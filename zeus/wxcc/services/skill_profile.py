import re
import logging
from collections import defaultdict
from copy import deepcopy
from zeus import registry as reg
from .. import wxcc_models as wm
from .shared import WxccBulkSvc, WxccBulkTask
from zeus.services import BrowseSvc, ExportSvc, DetailSvc, UploadTask, RowLoadResp

log = logging.getLogger(__name__)


@reg.bulk_service("wxcc", "skill_profiles", "CREATE")
class WxccSkillProfileCreateSvc(WxccBulkSvc):

    def run(self):
        payload = self.build_payload()
        self.current = self.client.skill_profiles.create(payload=payload)

    def build_payload(self) -> dict:
        active_skills = WxccBuildActiveSkillsTask(self).run()
        payload = {
            "name": self.model.name,
            "description": self.model.description,
            "activeSkills": active_skills,
        }
        return payload


@reg.bulk_service("wxcc", "skill_profiles", "UPDATE")
class WxccSkillProfileUpdateSvc(WxccBulkSvc):

    def run(self):
        self.current = self.lookup.skill_profile(self.model.name)

        payload = self.build_payload()

        self.client.skill_profiles.update(self.current["id"], payload)

    def build_payload(self) -> dict:
        active_skills = WxccBuildActiveSkillsTask(self).run()
        current_ver = int(self.current.get("version", 0))

        payload = {
            "id": self.current["id"],
            "name": self.model.name,
            "description": self.model.description,
            "activeSkills": active_skills,
            "version": current_ver + 1,
        }

        return payload


@reg.bulk_service("wxcc", "skill_profiles", "DELETE")
class WxccSkillProfileDeleteSvc(WxccBulkSvc):

    def run(self):
        self.current = self.lookup.skill_profile(self.model.name)
        self.client.skill_profiles.delete(self.current["id"])


class WxccBuildActiveSkillsTask(WxccBulkTask):
    """
    Parse the WxccSkillProfile.skills value to build the activeSkills array for a CREATE or UPDATE
    request.

    The payload is constructed based on the `WxccSkillProfile.skill_action` value which is one of:

    - `ADD`: Payload includes existing entries with skills from the model appended. No
             changes are made to existing entries.
    - `REPLACE`: Payload includes only entries from the model
    - `REMOVE`: Payload includes existing entries not found in the model

    NOTE: An entry associated with an existing assignment must include the `id` of the existing
    assignment.

    Returns:
         List of dicts for each skill/value pair in the skills string.
    """

    @property
    def current_active_skills(self) -> list[dict]:
        return self.svc.current.get("activeSkills") or []

    def run(self) -> list:
        if self.model.skill_action == "REMOVE":
            return self.build_active_skills_for_remove()
        elif self.model.skill_action == "REPLACE":
            return self.build_active_skills_for_replace()
        else:
            return self.build_active_skills_for_add()

    def build_active_skills_for_add(self):
        payload = deepcopy(self.current_active_skills)
        current_by_skill_id = {a["skillId"]: a for a in payload}

        for skill in self.model.skills:
            resp = self.svc.lookup.skill(skill.name)
            value_key = f"{resp['skillType'].lower()}Value"

            if resp["id"] in current_by_skill_id:
                continue

            payload.append({"skillId": resp["id"], value_key: skill.value})

        return payload

    def build_active_skills_for_replace(self):
        payload = []
        current_by_skill_id = {a["skillId"]: a for a in self.current_active_skills}

        for skill in self.model.skills:
            resp = self.svc.lookup.skill(skill.name)
            value_key = f"{resp['skillType'].lower()}Value"
            payload_entry = {"skillId": resp["id"], value_key: skill.value}

            if resp["id"] in current_by_skill_id:
                payload_entry["id"] = current_by_skill_id[resp["id"]]["id"]

            payload.append(payload_entry)

        return payload

    def build_active_skills_for_remove(self):
        current_by_skill_id = {a["skillId"]: a for a in self.current_active_skills}

        for skill in self.model.skills:
            resp = self.svc.lookup.skill(skill.name)

            current_by_skill_id.pop(resp["id"], None)

        return list(current_by_skill_id.values())


@reg.upload_task("wxcc", "skill_profiles")
class WbxcSkillProfileUploadTask(UploadTask):

    def validate_row(self, idx: int, row: dict):
        try:
            row["skills"] = self.build_skills(row)
        except Exception as exc:
            return RowLoadResp(index=idx, error=str(exc))

        return super().validate_row(idx, row)

    @staticmethod
    def build_skills(row):
        """Create Skill models for each set of Skill Name X and Skill Value X columns in the row."""
        skills = []
        for key in row:
            if m := re.search(r"Skill\s*Name\s*(\d+)", key, re.I):

                if not row[key]:
                    continue

                idx = m.group(1)
                obj = {"idx": idx}

                for wb_key, field in wm.WxccActiveSkill.indexed_wb_keys(idx).items():
                    if wb_key in row:
                        obj[field.name] = row[wb_key]

                skills.append(wm.WxccActiveSkill.parse_obj(obj))

        return skills


@reg.browse_service("wxcc", "skill_profiles")
class WxccSkillProfileBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = WxccSkillProfileBuilder(self.client)

        for resp in self.client.skill_profiles.list():
            model = builder.build_model(resp)

            row = model.dict()
            row["detail_id"] = resp["id"]
            row["skills_count"] = (
                len(resp.get("activeSkills", [])) + len(resp.get("activeEnumSkills", []))
            )
            rows.append(row)

        return rows


@reg.detail_service("wxcc", "skill_profiles")
class WxccSkillProfileDetailSvc(DetailSvc):

    def run(self):
        builder = WxccSkillProfileBuilder(self.client)

        resp = self.client.skill_profiles.get(self.browse_row["detail_id"])
        return builder.build_detail_model(resp)


@reg.export_service("wxcc", "skill_profiles")
class WxccSkillProfileExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = wm.WxccSkillProfile.schema()["data_type"]
        builder = WxccSkillProfileBuilder(self.client)

        for resp in self.client.skill_profiles.list():
            try:
                model = builder.build_detail_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class WxccSkillProfileBuilder:
    def __init__(self, client):
        self.client = client
        self._skill_map: dict | None = None
        self._enum_skill_map: None | dict[str, tuple[str, str]] = None

    @staticmethod
    def build_model(resp: dict):
        return wm.WxccSkillProfile.safe_build(resp, skills=[])

    def build_detail_model(self, resp: dict):
        active_skills = self.build_active_skills(resp)
        active_skills.extend(self.build_active_enum_skills(resp))

        skills = []
        for idx, item in enumerate(active_skills, 1):
            skills.append(wm.WxccActiveSkill(**item))

        return wm.WxccSkillProfile.safe_build(resp, skills=skills)

    def build_active_enum_skills(self, resp: dict) -> list[dict]:
        """
        Convert the activeSkills array  into dictionaries to be used to
        create WxccActiveSkill instances.

        Each object in the activeEnumSkills array includes an `enumSkillValueId`
        value that corresponds to a `skillId` in the parent skill's `enumSkillValues` array.

        NOTE: these IDs are not the skill's unique ID. They are IDs for the enum skill's values.
        There is currently no way to GET the skill through the API directly using anything in the skill
        profile's response.

        To find the associated skill, the enum skill value IDs from the active skill are compared
        against the values in the skill responses.

        Example:
            ```
            "activeEnumSkills": [
                {
                    "id": "a3edc8d9-a5a3-415c-a323-7889dc27fd44",
                    "enumSkillValueId": "78dadc44-ce31-477c-a7d1-08d2cbb08542",
                },
                {
                    "id": "cacdf5d9-5110-4b6c-be1d-afd3817a080b",
                    "enumSkillValueId": "057f7cbf-5f42-4ad6-b657-a518df980abf",
                },
                {
                    "id": "7c538228-c909-4e4e-8e1c-756f69a40b3c",
                    "enumSkillValueId": "c1cea899-b68b-411a-8c63-2c2c9ec752f4",
                },
            ]

           {
                "active": True,
                "description": "",
                "enumSkillValues": [
                    {
                        "createdTime": 1732729318481,
                        "id": "c1cea899-b68b-411a-8c63-2c2c9ec752f4",
                        "lastUpdatedTime": 1732729318481,
                        "links": [],
                        "name": "V2",
                        "skillId": "94696fb0-c4e0-4473-a3f3-1b119ab6b0db",
                    },
                    {
                        "createdTime": 1732729318483,
                        "id": "78dadc44-ce31-477c-a7d1-08d2cbb08542",
                        "lastUpdatedTime": 1732729318483,
                        "links": [],
                        "name": "V3",
                        "skillId": "94696fb0-c4e0-4473-a3f3-1b119ab6b0db",
                    },
                    {
                        "createdTime": 1732729318479,
                        "id": "057f7cbf-5f42-4ad6-b657-a518df980abf",
                        "lastUpdatedTime": 1732729318479,
                        "links": [],
                        "name": "V1",
                        "skillId": "94696fb0-c4e0-4473-a3f3-1b119ab6b0db",
                    },
                ],
                "id": "94696fb0-c4e0-4473-a3f3-1b119ab6b0db",
                "lastUpdatedTime": 1732729319000,
                "links": [],
                "name": "Test Enum Skill",
                "serviceLevelThreshold": 0,
                "skillType": "ENUM",
            }
            ```
        """
        active_skills = []
        enum_skills = defaultdict(list)
        resp_skills = resp.get("activeEnumSkills") or []

        for item in resp_skills:
            skill_name, enum_name = self.enum_skill_map[item["enumSkillValueId"]]
            enum_skills[skill_name].append(enum_name)
        skill_idx = 1
        for skill_name in enum_skills:

            value = ";".join(enum_skills[skill_name])

            active_skills.append(
                dict(
                    idx=skill_idx,
                    name=skill_name,
                    value=value,
                    type="ENUM",
                )
            )
            skill_idx += 1

        return active_skills

    def build_active_skills(self, resp: dict) -> list[dict]:
        """
        Convert the activeEnumSkills array into dictionaries to be used to
        create WxccActiveSkill instances.

        Each object in the activeSkills array includes a `skillId` property used to get the
        skill details. From the skill details the skill name and type are determined.

        The value is then taken from the value property associated with the skill type.

        Example:
            ```
            active_skills = [
              {
                    "id": "121",
                    "organizationId": "121",
                    "skillId": "1",
                    "booleanValue": False,
                    "proficiencyValue": 1,
                    "createdTime": 1617536243998,
                    "lastUpdatedTime": 1617536243998,
                    "version": {},
                }
            ]

            skill =  {
                "id": 1,
                "name": "Zeus Test Skill",
                "serviceLevelThreshold": 28,
                "active": True,
                "skillType": 'BOOLEAN'
            }
            ```
        """
        active_skills = []
        resp_skills = resp.get("activeSkills") or []
        skill_idx = 1

        for item in resp_skills:
            skill = self.skill_map[item["skillId"]]

            name = skill["name"]
            type_ = skill["skillType"].lower()
            value = item.get(f"{type_}Value", "NOTFOUND")

            active_skills.append(
                dict(
                    idx=skill_idx,
                    name=name,
                    value=value,
                    type=skill["skillType"],
                )
            )
            skill_idx += 1

        return active_skills

    @property
    def skill_map(self) -> dict:
        """
        Upon first call, perform a skill LIST request to
        create a mapping for skill IDs to skill objects then
        return the skill object matching the provided skill ID.
        """
        if self._skill_map is None:
            self._skill_map = {skill["id"]: skill for skill in self.client.skills.list()}

        return self._skill_map

    @property
    def enum_skill_map(self) -> dict[str, tuple[str, str]]:
        """
        Create a mapping dictionary of enum skill value entries keyed by the
        entry ID with values a tuple of skill name and enum name.
        """
        if self._enum_skill_map is None:
            self._enum_skill_map = {}

            for skill in self.skill_map.values():
                enum_skill_values = skill.get("enumSkillValues") or []

                if not enum_skill_values:
                    continue

                for item in enum_skill_values:
                    self._enum_skill_map[item["id"]] = (skill["name"], item["name"])

        return self._enum_skill_map
