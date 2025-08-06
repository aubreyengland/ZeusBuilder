from pydantic import BaseModel
from typing import Optional




class ParsedAddress(BaseModel):
    address_line1: str
    address_line2: Optional[str] = ""
    city: str
    state: str
    zip_code: str

class StoreData(BaseModel):
    corp_number: str
    physical_address: str
    region: Optional[str] = None  # This will be computed from corp_number
    parsed_address: Optional[ParsedAddress] = None
    site_name: Optional[str] = None
    

    @property
    def name(self) -> str:
        return f"CORP {self.corp_number} {self.region}" if self.region else f"CORP {self.corp_number}"

    @classmethod
    def from_extracted(cls, corp_number: str, physical_address: str, common_name:str = "", region: Optional[str] = None):
        lines = physical_address.strip().splitlines()
        address_line1 = ""
        address_line2 = ""
        city = state = zip_code = ""

        if len(lines) >= 2:
            # Multi-line format
            address_line1 = lines[0].strip()
            second_line = lines[1].strip()

            if "," in second_line:
                city_part, rest = second_line.split(",", 1)
                city = city_part.strip()
                state_zip_parts = rest.strip().split()
                if len(state_zip_parts) >= 2:
                    state = state_zip_parts[0]
                    zip_code = state_zip_parts[1].split("-")[0]  # Trim ZIP+4 if needed
        else:
            # Single-line format: Street, City, ST ZIP
            full_line = lines[0] if lines else physical_address.strip()
            if full_line.count(",") >= 2:
                street_part, city_part, state_zip = [p.strip() for p in full_line.split(",", 2)]
                address_line1 = street_part
                city = city_part
                state_zip_parts = state_zip.strip().split()
                if len(state_zip_parts) >= 2:
                    state = state_zip_parts[0]
                    zip_code = state_zip_parts[1].split("-")[0]
            else:
                # Fallback to whole string as address
                address_line1 = full_line

        parsed = ParsedAddress(
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            state=state,
            zip_code=zip_code
        )

        return cls(
            corp_number=corp_number,
            physical_address=physical_address,
            parsed_address=parsed,
            region=region,
            common_name=common_name
        )
        
    
class StoreCommonArea(BaseModel):
    # read from the Zoom Import Sheet Tab
    corp_number: str
    name: str = None
    extension: Optional[str] = None
    
class StoreCallQueue(BaseModel):
    # read from the Zoom CQs tab
    name: str
    site_name: Optional[str]  # Changed Opstr to Optional[str]
    corp_number: str
    extension: str
    members: str
    
    
    
class StoreSharedLineGroup(BaseModel):
    corp_number: str
    name: str
    extension: str
    members: str
    site_name: str  # Add this field
    
class StoreDevice(BaseModel):
    corp_number: str
    name: str
    site_name: Optional[str] = ""
    extension: str
    phone: Optional[str]
    phone_model: Optional[str]
    phone_provision_template: str
    device_type: Optional[str] = ""
    device_model: Optional[str] = ""
    mac_address: Optional[str] = ""
    assignee: Optional[str] = ""