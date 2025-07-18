import re
import logging
from zeus import registry as reg
from zeus.exceptions import ZeusBulkOpFailed
from zeus.wbxc import wbxc_models as wm
from zeus.shared import request_builder as rb
from zeus.wbxc.wbxc_simple import WbxcSimpleClient
from .supported_devices import build_supported_devices_map, normalized_model
from zeus.services import ExportSvc, UploadTask, RowLoadResp
from .shared import WbxcBulkSvc, WbxcLookup
from ...shared.helpers import deep_get

log = logging.getLogger(__name__)


@reg.bulk_service("wbxc", "device_settings", "UPDATE")
class WbxcDeviceSettingsUpdateSvc(WbxcBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: wm.WbxcDeviceSettings = model
        self.current_settings: dict = {}
        self.model_support_data: dict = {}
        self.device_type = ""

    def run(self):
        self.get_current()
        self.get_model_support_data()
        self.verify_settings_support()
        self.update_device_settings()

    def get_current(self):
        """
        Look up the device to get the ID and model, then attempt to get the current device settings.
        This will raise an exception if the model does not support settings customization.
        """
        self.current = self.lookup.device(self.model.mac)
        self.current_settings = self.client.device_settings.get(self.current["id"], deviceModel=self.current["product"])

    def get_model_support_data(self):
        model_str = normalized_model(self.current["product"])
        supported_devices = build_supported_devices_map()
        if model_str in supported_devices:
            self.model_support_data = supported_devices[model_str]
            self.device_type = self.model_support_data.get("type", "").lower()

    def verify_settings_support(self):
        """
        Verify the device is 'mpp' or 'ata' so we know which payload
        methods to use.
        """
        if not self.model_support_data:
            raise ZeusBulkOpFailed(f"Unsupported device model: {self.current['product']}")

        if self.device_type not in ("mpp", "ata"):
            raise ZeusBulkOpFailed(f"Unknown device type: {self.device_type}")

    def update_device_settings(self):
        payload = self.build_payload()
        if payload:
            self.client.device_settings.update(
                self.current["id"],
                deviceModel=self.current["product"],
                payload=payload,
            )

    def build_payload(self):
        if self.model.custom_enabled == "N":
            return {"customEnabled": False}

        custom_enabled = True if self.model.custom_enabled == "Y" else self.current_settings["customEnabled"]

        if self.device_type == "mpp":
            customizations = self.build_mpp_payload()

        else:
            customizations = self.build_ata_payload()

        return {
            "customEnabled": custom_enabled,
            "customizations": {self.device_type: customizations}
        }

    def build_mpp_payload(self):
        mpp_payload = {}
        fields = [
            rb.ChangedField("pnacEnabled", "pnac_enabled"),
            rb.ChangedField("activeCallFocusEnabled", "active_call_focus"),
            rb.ChangedField("callsPerLine", "calls_per_line"),
            rb.ChangedField("cdpEnabled", "cdp_enabled"),
            rb.ChangedField("iceEnabled", "ice_enabled"),
            rb.ChangedField("lldpEnabled", "lldp_enabled"),
            rb.ChangedField("dndServicesEnabled", "dnd_enabled"),
            rb.ChangedField("allowMonitorLinesEnabled", "monitor_list_enabled"),
            rb.ChangedField("mppUserWebAccessEnabled", "web_access"),

        ]
        current = deep_get(self.current_settings, "customizations.mpp", default={})
        builder = rb.RequestBuilder(
            fields=fields,
            data=self.model.to_payload(drop_unset=True),
            current=current,
        )
        if builder.payload_is_changed():
            mpp_payload = builder.payload()

        mpp_payload.update(self.build_enhanced_mcast_payload())

        return mpp_payload

    def build_ata_payload(self):
        fields = [
            rb.ChangedField("cdpEnabled", "cdp_enabled"),
            rb.ChangedField("lldpEnabled", "lldp_enabled"),
            rb.ChangedField("webAccessEnabled", "web_access"),

        ]
        current = deep_get(self.current_settings, "customizations.ata", default={})
        builder = rb.RequestBuilder(
            fields=fields,
            data=self.model.to_payload(drop_unset=True),
            current=current,
        )
        if builder.payload_is_changed():
            return builder.payload()

        return {}

    def build_enhanced_mcast_payload(self):
        """
        Create the 'enhancedMulticast' payload object based on the
        related model field values.

        This consists of an 'xmlAppUrl' string property and a 'multicastList'
        object array property.

        The entries in the 'multicastList' array are based on
        WbxcDeviceEnhancedMultiCastDestination objects in the model. If any
        are present, they replace any current 'multicastList' entries.

        The model.enhanced_mcast_enabled field = 'N' indicates that enhanced
        multicast should be disabled by removing any existing objects in the multicastList.

        If model.enhanced_mcast_enabled is empty, return an empty payload
        """
        payload = {}
        if self.model.enhanced_mcast_enabled == "N":
            payload = {"enhancedMulticast": {"multicastList": []}}

        elif self.model.enhanced_mcast_enabled == "Y":
            multicast_list = []
            for dest in self.model.enhanced_mcast_destinations:
                entry = {
                    "hostAndPort": dest.destination,
                    "hasXmlAppUrl": True if dest.xmlapp == "Y" else False
                }
                if dest.timer:
                    entry["xmlAppTimeout"] = dest.timer

                multicast_list.append(entry)

            payload = {"enhancedMulticast": {"multicastList": multicast_list}}

            if self.model.enhanced_mcast_url:
                payload["enhancedMulticast"]["xmlAppUrl"] = self.model.enhanced_mcast_url

        return payload


@reg.upload_task("wbxc", "device_settings")
class WbxcDeviceSettingsUploadTask(UploadTask):
    def validate_row(self, idx: int, row: dict):
        try:
            row["enhanced_mcast_destinations"] = self.build_enhanced_multicast_destinations(row)
        except Exception as exc:
            return RowLoadResp(index=idx, error=str(exc))
        return super().validate_row(idx, row)

    @staticmethod
    def build_enhanced_multicast_destinations(row):
        destinations = []
        for key in row:
            if m := re.search(r"Enhanced Multicast\s(\d+)\sDestination", key, re.I):

                if not row[key]:
                    continue

                idx = m.group(1)
                obj = {"idx": idx}

                for wb_key, field in wm.WbxcDeviceEnhancedMultiCastDestination.indexed_wb_keys(idx).items():
                    if wb_key in row:
                        obj[field.name] = row[wb_key]

                destinations.append(wm.WbxcDeviceEnhancedMultiCastDestination.parse_obj(obj))

        return destinations


@reg.export_service("wbxc", "device_settings")
class WbxcDeviceSettingsExportTask(ExportSvc):
    def run(self):
        rows = []
        errors = []
        data_type = wm.WbxcDeviceSettings.schema()["data_type"]
        builder = WbxcDeviceSettingsModelBuilder(self.client)

        params = {"type": "phone"}
        for resp in self.client.devices.list(**params):

            if builder.model_supports_settings(resp):
                try:
                    model = builder.build_model(resp)
                    rows.append(model)
                except Exception as exc:
                    error = getattr(exc, "message", str(exc))
                    errors.append({"name": self.error_row_name(resp), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}

    @staticmethod
    def error_row_name(resp):
        """
        Construct the most useful identifier from the list response.
        Use MAC address if present, otherwise use displayName or id.
        Include model if present as well.
        """
        mac = resp.get("mac", "")
        display = resp.get("displayName", "")
        model = resp.get("product", "unknown model")
        name = mac or display or resp["id"]
        return f"{name} ({model})"


class WbxcDeviceSettingsModelBuilder:
    def __init__(self, client):
        self.client: WbxcSimpleClient = client
        self.lookup = WbxcLookup(client)
        self._device_settings_models: list = []

    @property
    def device_settings_models(self) -> dict:
        """
        Get phone models that support customizable device settings based
        on the deviceSettingsConfiguration == WEBEX_CALLING_DEVICE_CONFIGURATION
        in the supported devices response.
        """
        if not self._device_settings_models:
            for model, details in build_supported_devices_map().items():
                if details.get("deviceSettingsConfiguration") == "WEBEX_CALLING_DEVICE_CONFIGURATION":
                    self._device_settings_models.append(model)
        return self._device_settings_models

    def model_supports_settings(self, resp: dict) -> bool:
        model_str = normalized_model(resp["product"])
        return model_str in self.device_settings_models

    def build_model(self, dev: dict):
        resp = self.client.device_settings.get(dev["id"], deviceModel=dev["product"])
        customizations = resp.get("customizations", {})
        data = customizations.get("mpp") or customizations.get("ata") or {}
        return wm.WbxcDeviceSettings.safe_build(
            mac=dev["mac"],
            custom_enabled=resp.get("customEnabled", ""),
            pnac_enabled=data.get("pnacEnabled", ""),
            active_call_focus=data.get("activeCallFocusEnabled", ""),
            calls_per_line=data.get("callsPerLine", ""),
            cdp_enabled=data.get("cdpEnabled", ""),
            lldp_enabled=data.get("lldpEnabled", ""),
            dnd_enabled=data.get("dndServicesEnabled", ""),
            ice_enabled=data.get("iceEnabled", ""),
            monitor_list_enabled=data.get("allowMonitorLinesEnabled", ""),
            web_access=data.get("mppUserWebAccessEnabled", ""),
            enhanced_mcast_destinations=self.build_enhanced_multicast_destinations(data),
            **self.build_enhanced_multicast(data),
        )

    @staticmethod
    def build_enhanced_multicast(customizations):
        mcast_url = deep_get(customizations, "enhancedMulticast.xmlAppUrl", default="")
        mcast_enabled = "Y" if mcast_url else "N"

        return {
            "enhanced_mcast_enabled": mcast_enabled,
            "enhanced_mcast_url": mcast_url,
        }

    @staticmethod
    def build_enhanced_multicast_destinations(customizations):
        destinations = []
        mcast_list = deep_get(customizations, "enhancedMulticast.multicastList", default=[])
        for idx, item in enumerate(mcast_list, 1):
            dest = wm.WbxcDeviceEnhancedMultiCastDestination(
                idx=idx,
                destination=item.get("hostAndPort", "UNKNOWN"),
                xmlapp=item.get("hasXmlAppUrl")
            )
            destinations.append(dest)

        return destinations
