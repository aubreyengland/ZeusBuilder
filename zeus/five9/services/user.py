import logging
from zeus import registry as reg
from typing import List, Optional
from zeus.five9 import five9_models as fm
from zeus.shared import data_type_models as dm
from zeus.exceptions import ZeusBulkOpFailed
from .shared import Five9BulkSvc, Five9BulkTask
from zeus.five9.five9_client import F9UserInfo, F9MediaType
from zeus.services import BrowseSvc, ExportSvc, WorksheetLoadResp, UploadTask
from zeus.shared.helpers import deep_get, ensure_all_rows_include_all_columns

log = logging.getLogger(__name__)


@reg.bulk_service("five9", "users", "CREATE")
class Five9UserCreateSvc(Five9BulkSvc):

    def run(self):
        payload = self.build_payload()
        self.client.createUser(UserInfo=payload)

    def build_payload(self):
        builder = Five9UserPayload(self.model)
        return {
            "generalInfo": builder.build_gen_info(),
            "skills": builder.build_skills(),
            "roles": builder.build_roles(),
            "agentGroups": [],
            "cannedReports": [],
        }


@reg.bulk_service("five9", "users", "UPDATE")
class Five9UserUpdateSvc(Five9BulkSvc):

    def run(self):
        self.current = self.get_current()
        for task_cls in (
                Five9UserUpdateTask,
                Five9UserSkillRemoveTask,
                Five9UserSkillAssignTask,
        ):
            task = task_cls(self)
            task.run()
            self.rollback_tasks.append(task)

    def get_current(self):
        """
        Look for a unique existing user for the userName in the request.

        Five9 API getUsersInfo request does pattern matching on userName so a
        userName of 'joe1' would return users 'joe1' and 'joe11' if they both existed.

        if multiple results (or no results) are returned for the userName, raise
        exception
        """
        res = list(self.client.getUsersInfo(userNamePattern=self.model.userName))

        if not res:
            raise ZeusBulkOpFailed(f"Existing user '{self.model.userName}' not found")

        if len(res) > 1:
            raise ZeusBulkOpFailed(
                f"Request for user: '{self.model.userName}' returned multiple results"
            )

        return res[0]


class Five9UserPayload:
    """
    Common methods to build CREATE and UPDATE payloads for Five9 Users
    """

    def __init__(self, model):
        self.model: fm.Five9User = model

    def build_payload(self):
        return {
            "generalInfo": self.build_gen_info(),
            "skills": self.build_skills(),
            "roles": self.build_roles(),
            "agentGroups": [],
            "cannedReports": [],
        }

    def build_gen_info(self):
        include = {
            "EMail",
            "userName",
            "extension",
            "lastName",
            "firstName",
            "userProfile",
            "federationId",
            "canChangePassword",
            "mustChangePassword",
        }
        gen_info = self.model.to_payload(include=include)
        gen_info["active"] = True
        gen_info["fullName"] = f"{self.model.firstName} {self.model.lastName}"
        gen_info["mediaTypeConfig"] = {"mediaTypes": self.build_media_types()}

        if self.model.password:
            gen_info["password"] = self.model.password

        return gen_info

    def build_media_types(self):
        """
        Create F9MediaType objects for API requests from the related
        values from a Five9User object
        """
        media_types = []

        for api_type, batch_attr in fm.media_types_map.items():

            val = getattr(self.model, batch_attr, 0)
            try:
                val = int(val)
            except Exception:
                raise ZeusBulkOpFailed(f"{api_type.title()} must be an integer")

            enabled = val > 0

            media_types.append(
                {
                    "enabled": enabled,
                    "intlligentRouting": False,
                    "maxAlowed": val,
                    "type": api_type,
                }
            )

        return media_types

    def build_roles(self) -> dict:
        """
        Construct the roles attribute for a user create or update request
        based on the administrator, supervisor, agent, report permissions and alwaysRecorded values.

        Permissions are included in the payload only if set on the model. An empty permissions
        attribute on the model will not cause all permissions to be removed.
        """
        roles = {
            "agent": {
                "alwaysRecorded": dm.yn_to_bool(self.model.alwaysRecorded),
                "attachVmToEmail": False,
                "sendEmailOnVm": False,
            }
        }
        if self.model.agent_permissions:
            roles["agent"]["permissions"] = [p.to_payload() for p in self.model.agent_permissions]

        if self.model.admin_permissions:
            roles["admin"] = {"permissions": [p.to_payload() for p in self.model.admin_permissions]}

        if self.model.supervisor_permissions:
            roles["supervisor"] = {"permissions": [p.to_payload() for p in self.model.supervisor_permissions]}

        if self.model.reporting_permissions:
            roles["reporting"] = {"permissions": [p.to_payload() for p in self.model.reporting_permissions]}

        return roles

    def build_roles_to_remove(self) -> list:
        """
        Role removal is signaled by assignment of a permission profile
        without any permissions defined
        """
        roles_to_remove = []

        if self.model.admin_permissions_name and not self.model.admin_permissions:
            roles_to_remove.append("DomainAdmin")

        if self.model.supervisor_permissions_name and not self.model.supervisor_permissions:
            roles_to_remove.append("Supervisor")

        return roles_to_remove

    def build_skills(self) -> list:
        if self.model.skills == "~" or not self.model.skills:
            return []
        return parse_skill_level_strings(self.model.skills)


@reg.bulk_service("five9", "users", "DELETE")
class Five9UserDeleteSvc(Five9BulkSvc):

    def run(self):
        self.client.deleteUser(self.model.userName)


class Five9UserSkillAssignTask(Five9BulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.current = svc.current
        self.assigned_skills = []

    def run(self):
        for skill in self.get_skills_to_assign():
            skill["userName"] = self.model.userName
            self.client.userSkillAdd(skill)
            self.assigned_skills.append(skill)

    def get_skills_to_assign(self):
        current_skills = [skill.dict() for skill in self.current.skills]
        return get_skills_to_add(self.model.skills, current_skills)


class Five9UserSkillRemoveTask(Five9BulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.current = svc.current
        self.removed_skills = []

    def run(self):
        for skill in self.get_skills_to_remove():
            self.client.userSkillRemove(skill)
            self.removed_skills.append(skill)

    def get_skills_to_remove(self):
        current_skills = [skill.dict() for skill in self.current.skills]
        return get_skills_to_remove(self.model.skills, current_skills)


class Five9UserUpdateTask(Five9BulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.current = svc.current

    def run(self):
        payload = self.build_payload()
        self.client.modifyUser(**payload)

    def build_payload(self):
        builder = Five9UserPayload(self.model)
        return {
            "userGeneralInfo": builder.build_gen_info(),
            "rolesToSet": builder.build_roles(),
            "rolesToRemove": builder.build_roles_to_remove(),
        }


def get_skills_to_add(request_skills: str, current_skills: list) -> list:
    """
    Return a list of skill objects for skills in the request but not already
    assigned to the user.  The skill name and level must match to be considered
    already assigned.

    Args:
        request_skills (str): semi-separated Name=level pairs or '~' to remove all skills
        current_skills (list): List of dicts with skillName and level keys

    Returns:
        (list): List of skillName, level dicts
    """
    if request_skills == "~" or not request_skills:
        return []

    to_add = []
    request_skill_objs = parse_skill_level_strings(request_skills)
    current_skill_levels_by_name = {c["skillName"]: c["level"] for c in current_skills}

    for req_skill in request_skill_objs:
        matched_level = current_skill_levels_by_name.get(req_skill["skillName"])
        if req_skill["level"] != matched_level:
            to_add.append(req_skill)

    return to_add


def get_skills_to_remove(model_skills, current_skills) -> list:
    """
    Return a list of skill objects to remove from the user.
    If skills are specified in the request, any currently assigned skill
    that does not match the name and level of skills in the request is removed.

    If the request skills value is '~'.  All current skills are removed.
    """
    current_skills = [skill for skill in current_skills]

    if model_skills == "~":
        return current_skills

    if not model_skills:
        return []

    to_remove = []
    request_skills_by_name = {
        r["skillName"]: r for r in parse_skill_level_strings(model_skills)
    }

    for current in current_skills:
        match = request_skills_by_name.get(current["skillName"])

        if not match or match["level"] != current["level"]:
            to_remove.append(current)

    return to_remove


def parse_skill_level_strings(request_skills: str) -> list:
    """
    Parse the skill value from the workbook into a list of dicts with skillName
    and level keys.
    This function assumes the column value is a string of name=level pairs separated
    by semicolon. If not an exception is raised.

    Args:
        request_skills (str): semi-separated skill=level pairs

    Returns:
        skill_objs (list): List of dicts in format expected by Five9 API
    """
    skill_objs = []
    skills_levels_list = request_skills.split(";")
    try:
        for item in skills_levels_list:
            name, level = item.split("=")
            skill_objs.append({"skillName": name.strip(), "level": int(level.strip())})

    except Exception as ex:
        msg = f"Skills: '{request_skills}' not formatted correctly"
        raise ZeusBulkOpFailed(msg)

    return skill_objs


@reg.upload_task("five9", "users")
class Five9UserUploadTask(UploadTask):
    priority = 9

    def run(self):
        permissions_by_role = self.parse_loaded_permission_rows()
        for row in self.rows:
            row["permissions_by_role"] = permissions_by_role

        super().run()

    def parse_loaded_permission_rows(self) -> dict:
        """
        Check for a permissions WorksheetLoadResp and, if found
        save the list of permission dicts in the
        `permissions_by_role` dict keyed by role and profile name.
        """
        permissions_by_role = {role: {} for role in fm.FIVE9_ROLES}
        permissions_data_type = fm.Five9PermissionProfile.schema()["data_type"]

        perm_resp: WorksheetLoadResp = self.svc.worksheet_responses.get(permissions_data_type)
        if perm_resp:
            for row_resp in perm_resp.loaded_rows:
                if row_resp.error:
                    continue

                name: str = str(row_resp.data.name).lower()
                role: str = str(row_resp.data.role).lower()
                permissions: List[dict] = row_resp.data.permissions

                if role in permissions_by_role:
                    permissions_by_role[role][name] = permissions

        return permissions_by_role


@reg.browse_service("five9", "users")
class Five9UserBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        for item in self.client.getUsersGeneralInfo():
            # replace None with empty string
            row = {k: v or "" for k, v in item.dict().items()}
            rows.append(row)

        return rows


@reg.export_service("five9", "users")
class Five9UserExportSvc(ExportSvc):

    def __init__(self, client):
        super().__init__(client)
        self.users_resp = []
        self.roles = fm.FIVE9_ROLES
        self.permission_profile_builder = None
        self.permission_profiles: List[dict] = []

    def run(self) -> dict:
        """
        Get users and permission_profiles worksheet data for export
        Both data_types are built in this task because the permissions
        data is contained within the getUsersInfo responses.
        """
        user_data_type = fm.Five9User.schema()["data_type"]
        perm_data_type = fm.Five9PermissionProfile.schema()["data_type"]

        self.users_resp = list(self.client.getUsersInfo())
        self.permission_profile_builder = Five9PermissionProfileBuilder(self.users_resp)
        users = self.build_users()
        permissions = self.build_permissions()

        return {user_data_type: users, perm_data_type: permissions}

    def build_users(self):
        rows = []
        errors = []
        for user in self.users_resp:
            try:
                model = build_model(user)

                for role in self.roles:
                    attr = f"{role}_permissions_name"
                    profile = self.permission_profile_builder.lookup(user, role)

                    if profile:
                        profile_name = profile["name"]
                    else:
                        profile_name = ""

                    setattr(model, attr, profile_name)

                rows.append(model)
            except Exception as exc:
                name = deep_get(user, "generalInfo.EMail", default="unknown")
                error = getattr(exc, "message", str(exc))
                errors.append({"name": name, "error": error})

        return {"rows": rows, "errors": errors}

    def build_permissions(self):

        rows = []
        errors = []
        for item in self.permission_profile_builder.permission_profiles:
            try:
                perms = [fm.Five9Permission(**perm) for perm in item["permissions"]]
                rows.append(
                    fm.Five9PermissionProfile(name=item["name"], role=item["role"], permissions=perms)
                )
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": item.get("name", "unknown"), "error": error})

        return {"rows": rows, "errors": errors}


class Five9PermissionProfileBuilder:
    def __init__(self, users_resp):
        self.roles = fm.FIVE9_ROLES
        self.users_resp = users_resp
        self.permission_profiles = []
        self.collect_unique_permission_profiles()

    def collect_unique_permission_profiles(self):
        """
        Create a dictionary with the role, permissions and derived name
        for the unique sets of permissions for each role in the Five9 Org.
        """
        profiles = []
        for role in self.roles:
            for user in self.users_resp:
                if self.lookup(user, role):
                    # Already seen this set of permissions for this role
                    continue

                perms = self.get_sorted_permissions_for_user_role(user, role)

                if perms:
                    # New set of permissions for the role, create unique name and save
                    name = self.get_new_profile_name(role)
                    self.permission_profiles.append({"name": name, "role": role, "permissions": perms})

    def build_permissions(self):
        """
        Create rows for the Permissions worksheet from the unique permission sets
        collected.
        Each row has keys: Name: the unique profile name, Role: One of the `fm.FIVE9_ROLE` values
        along with multiple `Permission x` keys with x incremented for each permission.

        The permission values are in the form of `PermissionType=Y/N`.

        Since profiles of different roles will have differing number of permissions,
        the created rows are passed through the `ensure_all_rows_include_all_columns`
        function to add missing columns with empty values

        Returns:
            rows (list): List of dictionaries for Permissions worksheet rows
        """
        rows = []

        for profile in self.permission_profiles:
            row = {"Name": profile["name"], "Role": profile["role"]}

            for idx, perm in enumerate(profile["permissions"], 1):
                key = f"Permission {idx}"
                name = perm["type"]
                value = dm.to_wb_str(perm["value"])
                row[key] = f"{name}={value}"

            rows.append(row)

        return ensure_all_rows_include_all_columns(rows)

    def lookup(self, user, role) -> Optional[dict]:
        perms = self.get_sorted_permissions_for_user_role(user, role)
        if perms:
            return next((prof for prof in self.permission_profiles if prof["permissions"] == perms), None)
        return None

    @staticmethod
    def get_sorted_permissions_for_user_role(user, role):
        perms = deep_get(user, ["roles", role, "permissions"], default=None)
        if perms:
            return sorted(perms, key=lambda o: o["type"])
        return None

    def get_new_profile_name(self, role):
        idx = len([prof for prof in self.permission_profiles if prof["role"] == role]) + 1
        return f"{role.title()} Permission Profile {idx}"


def build_model(resp: F9UserInfo) -> fm.Five9User:
    """
    Create user model from api response.
    Fields firstName, lastName may be blank in API response but are
    required by model so set these to empty string.
    """
    model_obj = resp.generalInfo.dict()
    model_obj["skills"] = ";".join(f"{sk.skillName}={sk.level}" for sk in resp.skills)
    model_obj.update(user_roles_for_batch_user(resp.roles))

    media_types = media_types_for_batch_user(resp.generalInfo.mediaTypeConfig["mediaTypes"])
    model_obj.update(media_types)

    return fm.Five9User.safe_build(model_obj)


def media_types_for_batch_user(media_types: List[F9MediaType]) -> dict:
    """
    Convert F9MediaType objects into key/value pairs used
    in the Five9User object.
    """
    batch_media_types = {}

    for item in media_types:
        batch_attr = fm.media_types_map[item.type.upper()]
        batch_media_types[batch_attr] = item.maxAlowed or 0

    return batch_media_types


def user_roles_for_batch_user(roles: dict) -> dict:
    """
    Convert the dict from a F9UserInfo object to the
    key/values used to represent the roles in a Five9User object
    """
    supervisor = True if roles.get("supervisor") else False
    administrator = True if roles.get("admin") else False

    agent_roles = roles.get("agent") or {}
    if agent_roles.get("alwaysRecorded"):
        alwaysRecorded = True
    else:
        alwaysRecorded = False

    return dict(
        administrator=administrator, supervisor=supervisor, alwaysRecorded=alwaysRecorded
    )
