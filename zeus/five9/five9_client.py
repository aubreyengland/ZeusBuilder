import logging
import zeep.exceptions
from datetime import datetime
from pydantic import BaseModel
from requests import Session, auth
from zeep.helpers import serialize_object
from zeep import Client, transports, cache
from typing import Iterator, List, Literal, Optional, Dict

log = logging.getLogger(__name__)


class F9ClientBase(BaseModel):
    @classmethod
    def from_zeep(cls, obj):
        zdict = serialize_object(obj)
        return cls.parse_obj(zdict)


class F9Skill(F9ClientBase):
    """
    Five9 API data type used for:
     - modifySkill request
     - getSkill response
     - createSkill request (as part of skillInfo)
     - createSkill response (as part of skillInfo)
     - modifySkill response (as part of skillInfo)
     - getSkillInfo response (as part of skillInfo)
    """

    name: str
    id: int = None
    description: str = None
    messageOfTheDay: str = None
    routeVoiceMails: bool = False


class F9UserSkill(F9ClientBase):
    """
    Five9 API data type used for:
     - userSkillAdd request
     - userSkillRemove request
     - createSkill request (as part of skillInfo)
     - createSkill response (as part of skillInfo)
     - modifySkill response (as part of skillInfo)
     - getSkillInfo response (as part of skillInfo)
    """

    level: int
    skillName: str
    id: int = None
    userName: str = None


class F9SkillInfo(F9ClientBase):
    """
    Five9 API data type used for:
     - createSkill request
     - createSkill response
     - modifySkill response
     - getSkillInfo response
    """

    skill: F9Skill
    users: List[F9UserSkill] = []


class F9PromptInfo(F9ClientBase):
    """
    Five9 API data type used for:
     - addPromptWavInline request (as part of PromptWavInline object)
     - modifyPromptWavInline request (as part of PromptWavInline object)
     - addPromptTTS request (as part of PromptTTS object)
     - modifyPromptTTS request (as part of PromptTTS object)
     - getPrompt response
     - getPrompts response
    """

    name: str
    type: Literal["TTSGenerated", "PreRecorded"]
    description: str = None
    languages: list = []


class F9TTSInfo(F9ClientBase):
    """
    Five9 API data type used for:
     - addPromptTTS request (as part of PromptTTS object)
     - modifyPromptTTS request (as part of PromptTTS object)
    """

    text: str
    language: Optional[str] = None
    sayAs: str = "Default"
    sayAsFormat: str = "NoFormat"


class F9PromptTTS(F9ClientBase):
    """
    Five9 API data type used for:
     - addPromptTTS request
     - modifyPromptTTS request
    """

    prompt: F9PromptInfo
    ttsInfo: F9TTSInfo


class F9PromptWavInline(F9ClientBase):
    """
    Five9 API data type used for:
     - addPromptWavInline request
     - modifyPromptWavInline request
    """

    prompt: F9PromptInfo
    wavFile: str


class F9ReasonCode(F9ClientBase):
    """
    Five9 API data type used for:
     - createReasonCode request
     - modifyReasonCode request
     - getReasonCodeByType response
    """
    name: str
    enabled: bool
    paidTime: bool
    shortcut: str = None
    type: Literal["NotReady", "Logout"]


class F9CannedReport(F9ClientBase):
    """
    Five9 API data type used for cannedReports value on
    UserInfo data type
    """

    index: int
    name: str


class F9MediaType(F9ClientBase):
    """
    Five9 API data type used for the mediaTypeConfig value
    in UserGeneralInfo objects
    """
    enabled: bool
    type: str
    maxAlowed: int
    intlligentRouting: bool = False


class F9UserGeneralInfo(F9ClientBase):
    """
    Five9 API data type used for:
     - modifyUser request
     - createUser request (as part of UserInfo)
     - getUsersInfo response (as part of UserInfo)
     - createUser response (as part of UserInfo)
     - modifyUser response (as part of UserInfo)
    """

    EMail: str
    userName: str
    extension: str
    lastName: str = None
    fullName: str = None
    id: int = None
    active: bool = True
    firstName: str = None
    password: str = None
    IEXScheduled: bool = False
    osLogin: str = None
    locale: str = None
    startDate: datetime = None
    userProfileName: str = None
    federationId: str = None
    phoneNumber: str = None
    canChangePassword: bool
    mustChangePassword: bool
    mediaTypeConfig: Dict[Literal["mediaTypes"], List[F9MediaType]]


class F9UserInfo(F9ClientBase):
    """
    Five9 API data type used for:
     - createUser request
     - getUsersInfo response
     - createUser response
     - modifyUser response
    """

    agentGroups: List = []
    cannedReports: List[F9CannedReport] = []
    generalInfo: F9UserGeneralInfo
    skills: List[F9UserSkill] = []
    roles: dict = {}


class CallVariableRestriction(F9ClientBase):
    type: str
    value: str


class CallVariable(F9ClientBase):
    name: str
    type: str
    group: str
    reporting: bool
    sensitiveData: bool
    description: str = None
    defaultValue: str = None
    dispositions: list = []
    applyToAllDispositions: bool
    restrictions: List[CallVariableRestriction] = []


def zeep_transport(user, password, verify, timeout=300):
    session = Session()
    session.verify = verify
    session.auth = auth.HTTPBasicAuth(user, password)
    return transports.Transport(
        session=session,
        operation_timeout=timeout,
        cache=cache.SqliteCache()
    )


class Five9ServerFault(Exception):
    def __init__(self, message, code=None):
        self.message = message
        self.code = code


class Five9:
    wsdl = "https://api.five9.com/wsadmin/v12/AdminWebService?wsdl&user="

    def __init__(self, username, password, verify=True, wsdl=None):
        self.username = username
        self.history = zeep.plugins.HistoryPlugin()
        self.client = Client(
            wsdl=wsdl or self.wsdl,
            plugins=[self.history],
            transport=zeep_transport(username, password, verify),
        )

    def __repr__(self):
        return f"Five9(username={self.username})"

    def close_session(self):
        """
        Close sessions so that user can log in to Admin portal without being prompted
        """
        log.debug(f"Closed session to Five9")
        self.client.service.closeSession()

    def process_method(self, process_method, **kwargs):
        """
        Function that processes specific method
        Args:
            process_method: method to be processed
            kwargs: required parameters for some methods

        Returns:
            Executed Five9 Method
        """
        try:
            return process_method(**kwargs)

        except zeep.exceptions.Fault as exc:
            # Handle errors with JavaNullPointer trace stack in error message
            if "unsupported audio file" in str(exc.message).lower():
                message = "Unsupported Audio File"
            elif "internal server error" in str(exc.message).lower():
                message = "Five9 API server error"
            else:
                message = exc.message
            raise Five9ServerFault(message, exc.code)

        except TypeError as exc:
            # Raised if arguments do not match element in wsdl
            log.exception("Zeep Object Type Error")
            raise Five9ServerFault(f"Input incompatible with Five9 schema")

        finally:
            try:
                self.close_session()
            except Exception:
                pass

    def getApiVersions(self):
        method = self.client.service.getApiVersions
        return self.process_method(method)

    def getSkills(self, skillNamePattern: str = None) -> Iterator[F9Skill]:
        """
        Get Five9 skills matching the skillNamePattern or all skills if
        pattern is None.

        Yields:
            (Skill): Five9 Skill instance for each skill returned
        """
        method = self.client.service.getSkills
        for obj in self.process_method(method, skillNamePattern=skillNamePattern):
            # TODO: TEMP EXCEPTION BLOCK FOR TESTING LARGE ORG
            try:
                res = F9Skill.from_zeep(obj)
            except Exception:
                log.exception(f"F9Skill create failed for {obj}")
                continue
            yield res

    def getSkillInfo(self, skillNamePattern: str) -> F9SkillInfo:
        """
        Gets Five9 SkillInfo instance for the provided skill name.

        Args:
            skillNamePattern (str): skill name

        Returns:
            (F9SkillInfo): Five9 SkillInfo instance
        """
        method = self.client.service.getSkillInfo
        obj = self.process_method(method, skillName=skillNamePattern)
        return F9SkillInfo.from_zeep(obj)

    def createSkill(self, skillInfo: dict) -> F9SkillInfo:
        """
        Creates Five9 skill.
        The skillinfo dict includes the following keys:
        - skill (required): A dict with a name (required) and description (option) keys
        - users (optional): A list of dicts with userName (required) and level int (optional)

        Args:
            skillInfo (dict): Dictionary with skill name and users

        Returns:
            (F9SkillInfo): Five9 SkillInfo instance
        """
        method = self.client.service.createSkill
        obj = self.process_method(method, skillInfo=skillInfo)
        return F9SkillInfo.from_zeep(obj)

    def deleteSkill(self, skillName: str) -> None:
        """Deletes Five9 skill."""
        method = self.client.service.deleteSkill
        self.process_method(method, skillName=skillName)

    def modifySkill(self, skill: dict) -> F9SkillInfo:
        """
        Modifies Five9 skill.
        The skill dict includes the following keys:
        - name (required): string
        - description (optional): string
        - messageOfTheDay (optional): string
        - routeVoiceMails (required): True/False

        Args:
            skill (dict): Dictionary with skill values

        Returns:
            (F9SkillInfo): Five9 SkillInfo instance
        """
        obj = self.process_method(self.client.service.modifySkill, skill=skill)
        return F9SkillInfo.from_zeep(obj)

    def getUsersGeneralInfo(self, userNamePattern: str = None) -> Iterator[F9UserGeneralInfo]:
        """
        Returns general information about each username that matches a patter

        userNamePattern accepts a string with regex syntax for partial matches
        All users are returned if userNamePattern is not provided.

        Args:
            userNamePattern (str): Optional username search string

        Yields:
            (User): User instance for each returned user
        """
        method = self.client.service.getUsersGeneralInfo
        for obj in self.process_method(method, userNamePattern=userNamePattern):
            # TODO: TEMP EXCEPTION BLOCK FOR TESTING LARGE ORG
            try:
                res = F9UserGeneralInfo.from_zeep(obj)
            except Exception as exc:
                log.exception(f"F9UserInfo create failed for {obj}")
                continue
            yield res

    def getUsersInfo(self, userNamePattern: str = None) -> Iterator[F9UserInfo]:
        """
        Returns the same info from getUsersGeneralInfo with additional info:
         - agentGroups - the agent group where the user belongs.
         - cannedReports - Reports associated with the user.
         - roles - Roles assigned to the user. True means the role is enabled
         - skills - list of user skills with Skill ID, Name, and Level

        userNamePattern accepts a string with regex syntax for partial matches
        All users are returned if userNamePattern is not provided.

        Args:
            userNamePattern (str): Optional username search string

        Yields:
            (F9UserInfo): F9UserInfo instance for each returned user
        """
        method = self.client.service.getUsersInfo
        for obj in self.process_method(method, userNamePattern=userNamePattern):
            # TODO: TEMP EXCEPTION BLOCK FOR TESTING LARGE ORG
            try:
                res = F9UserInfo.from_zeep(obj)
            except Exception:
                log.exception(f"F9UserInfo create failed for {obj}")
                continue
            yield res

    def createUser(self, UserInfo: dict) -> F9UserInfo:
        """
        Creates Five9 user.
        Args:
            UserInfo (dict): UserInfo dictionary with the following keys:
             - generalInfo (required): userGeneralInfo dict
             - agentGroups (optional): agentGroups list
             - cannedReports (optional): cannedReports list
             - skills (optional): F9UserSkill list
             - roles (optional): roles dict

        Returns:
             (F9UserInfo): Five9 User instance
        """
        obj = self.process_method(self.client.service.createUser, userInfo=UserInfo)
        return F9UserInfo.from_zeep(obj)

    def deleteUser(self, userName: str) -> None:
        """
        Deletes Five9 user.

        Args:
            userName (str): Username to be deleted
        """
        self.process_method(self.client.service.deleteUser, userName=userName)

    def modifyUser(self, userGeneralInfo: dict, rolesToSet: dict, rolesToRemove: list) -> F9UserInfo:
        """
        Modifies Five9 user.
        Args:
            userGeneralInfo (dict): userGeneralInfo dict
            rolesToSet (dict): userRoles dict
            rolesToRemove (list): list of role types to be removed

        Returns:
             user (F9UserInfo): Five9UserInfo instance
        """
        user = self.process_method(
            self.client.service.modifyUser,
            userGeneralInfo=userGeneralInfo,
            rolesToSet=rolesToSet,
            rolesToRemove=rolesToRemove,
        )
        return F9UserInfo.from_zeep(user)

    def userSkillRemove(self, userSkill: dict) -> None:
        """
        Removes skill from user.

        Args:
            userSkill (dict): userSkill data type with keys:
             - id (optional)
             - level (required)
             - skillName (required)
             - userName (required)
        """
        self.process_method(
            self.client.service.userSkillRemove, userSkill=userSkill
        )

    def userSkillAdd(self, userSkill: dict) -> None:
        """
        Adds skills to user.

        Args:
            userSkill (dict): userSkill data type with keys:
             - id (optional)
             - level (required)
             - skillName (required)
             - userName (required)

        Returns:
            user: Five9 user object
        """
        self.process_method(
            self.client.service.userSkillAdd, userSkill=userSkill
        )

    def userSkillModify(self, userSkill: dict) -> None:
        """
        Modify existing skill level for user.

        Args:
            userSkill (dict): userSkill data type with keys:
             - id (optional)
             - level (required)
             - skillName (required)
             - userName (required)

        Returns:
            user: Five9 user object
        """
        self.process_method(
            self.client.service.userSkillModify, userSkill=userSkill
        )

    # User Profile
    # todo determine if needed and if so how should they be created
    def getUserProfiles(self, profile):
        """
        Gets Five9 User Profiles:
        Args:
            profile: profile Five9 object

        Returns:
            profile: Five9 object
        """
        profiles = self.process_method(
            self.client.service.getUserProfiles, userProfileNamePatern=profile
        )
        if profiles:
            for profile in profiles:
                yield profile

    def deleteUserProfile(self, profileName):
        """
        Deletes Five9 user profile
        Args:
            profileName: profileName
        """
        self.process_method(
            self.client.service.deleteUserProfile,
            userProfileName=profileName
        )

    def getDNISList(self, selectUnassigned: bool = False) -> List[str]:
        """
        Get DNIS's provisioned for the org and return them as a list of strings.

        Args:
            selectUnassigned (bool): Only return DNIS's not assigned to a campaign if True
        """
        return self.process_method(self.client.service.getDNISList, selectUnassigned=selectUnassigned)

    def getPrompts(self) -> Iterator[F9PromptInfo]:
        """
        Gets all Five9 prompts

        Yields:
            (PromptInfo): PromptInfo instance for each prompt returned
        """
        for obj in self.process_method(self.client.service.getPrompts):
            # TODO: TEMP EXCEPTION BLOCK FOR TESTING LARGE ORG
            # TODO: SHOULD BE REMOVED ONCE FIELD INCLUSION IS VERIFIED
            try:
                res = F9PromptInfo.from_zeep(obj)
            except Exception:
                log.exception(f"F9PromptInfo create failed for {obj}")
                continue
            yield res

    def getPrompt(self, promptName: str) -> F9PromptInfo:
        """
        Gets Five9 prompt matching the provided prompt name.

        Args:
            promptName (str): name of the prompt

        Yields:
            (PromptInfo): PromptInfo instance for prompt returned

        Raises:
            Five9ServerFault if name not found
        """
        obj = self.process_method(self.client.service.getPrompt, promptName=promptName)
        return F9PromptInfo.from_zeep(obj)

    def addPromptWavInline(self, prompt: dict, wavFile: bytes) -> None:
        """
        Create a Five9 Wav prompt using the provided promptInfo and
        upload the wav file at the provided path.

        promptInfo data type with the following keys:
        - name: The prompt name as a string (required)
        - description: prompt description as a string (optional)
        - languages: List of supported languages (optional)
        - type: Must be 'PreRecorded'

        Args:
             prompt(dict): Dictionary of promptInfo data type
             wavFile (str, Path): Path to the wav file as a string or Path object
        """
        self.process_method(
            self.client.service.addPromptWavInline,
            prompt=prompt,
            wavFile=wavFile,
        )

    def modifyPromptWavInline(self, prompt: dict, wavFile: bytes) -> None:
        """
        Modify the info and/or wav file for an existing Five9 Wav prompt.

        promptInfo data type includes the following:
        - name: The prompt name as a string (required)
        - description: prompt description as a string (optional)
        - languages: List of supported languages (optional)
        - type: Must be 'PreRecorded'

        wavFile is required by the API for modify operations

        Args:
             prompt(dict): Dictionary of promptInfo data type
             wavFile (None, str, Path): Path to the wav file as a string or Path object
        """
        method = self.client.service.modifyPromptWavInline
        self.process_method(method, prompt=prompt, wavFile=wavFile)

    def addPromptTTS(self, prompt: dict, ttsInfo: dict) -> None:
        """
        Creates Five9 TTS Prompt.

        promptInfo data type includes the following:
        - name: The prompt name as a string (required)
        - description: prompt description as a string (optional)
        - languages: List of supported languages (optional)
        - type: Must be 'PreRecorded'

        ttsInfo data type includes the following:
         - text (required): Text for the TTS recording
         - language (required): Prompt language
         - sayAs (required): Describes how letters, numbers, and symbols are pronounced.
           defaults to 'Default'
         - sayAsFormat (required): Date and time format of the prompt defaults to 'NoFormat'

        Args:
            prompt (dict): Dictionary of promptInfo data type
            ttsInfo (dict): Dictionary of ttsInfo data type
        """
        method = self.client.service.addPromptTTS
        self.process_method(method, prompt=prompt, ttsInfo=ttsInfo)

    def modifyPromptTTS(self, prompt: dict, ttsInfo: dict) -> None:
        """
        Modifies Five9 TTS Prompt.

        promptInfo data type includes the following:
        - name: The prompt name as a string (required)
        - description: prompt description as a string (optional)
        - languages: List of supported languages (optional)
        - type: Must be 'PreRecorded'

        ttsInfo data type includes the following:
         - text (required): Text for the TTS recording
         - language (required): Prompt language
         - sayAs (required): Describes how letters, numbers, and symbols are pronounced.
           defaults to 'Default'
         - sayAsFormat (required): Date and time format of the prompt defaults to 'NoFormat'

        Args:
            prompt (dict): Dictionary of promptInfo data type
            ttsInfo (dict): Dictionary of ttsInfo data type
        """
        self.process_method(
            self.client.service.modifyPromptTTS,
            prompt=prompt,
            ttsInfo=ttsInfo
        )

    def deletePrompt(self, promptName: str) -> None:
        """
        Deletes Five9 prompt.
        """
        self.process_method(self.client.service.deletePrompt, promptName=promptName)

    def getReasonCodeByType(self, reasonCodeName: str, type_: str) -> F9ReasonCode:
        """
        Gets Five9 Reason Code instance for the provided name and type.
        Both name and type must be provided.
        Valid types are: "NotReady", "Logout"
        """
        obj = self.process_method(
            self.client.service.getReasonCodeByType,
            reasonCodeName=reasonCodeName,
            type=type_,
        )
        return F9ReasonCode.from_zeep(obj)

    def createReasonCode(self, reasonCode) -> None:
        """ Creates Five9 Reason Code. No rv on successful create."""
        self.process_method(
            self.client.service.createReasonCode,
            reasonCode=reasonCode
        )

    def modifyReasonCode(self, reasonCode) -> None:
        """ Modifies an existing Five9 Reason Code. No rv on successful modify."""
        self.process_method(
            self.client.service.modifyReasonCode,
            reasonCode=reasonCode
        )

    def deleteReasonCodeByType(self, reasonCodeName: str, type_: str) -> None:
        """ Deletes Five9 reason code. No rv on successful deletion."""
        self.process_method(
            self.client.service.deleteReasonCodeByType,
            type=type_,
            reasonCodeName=reasonCodeName,
        )

    def getCallVariables(self, name=None, group=None) -> Iterator[CallVariable]:
        """
        Gets Five9 Call Variables
        Args:
            name: name of variable to get, leave blank to get all
            group: object of variable to get, leave blank to get all

        Returns:
            CallVariable: Custom object
        """
        call_vars = self.process_method(
            self.client.service.getCallVariables,
            namePattern=name,
            groupName=group
        )
        for obj in call_vars:
            yield CallVariable.from_zeep(obj)

    def createCallVariable(self, variable) -> None:
        """
        Creates Five9 Call Variables.
        Args:
            variable: object processed from the input BRD spreadsheet
        """
        self.process_method(
            self.client.service.createCallVariable,
            variable=variable
        )

    def deleteCallVariable(self, name: str, groupName: str) -> None:
        """
        Deletes Five9 call variable
        Args:
            name (str): Name of variable to be deleted
            groupName (str): Group name of call variable.
        """
        self.process_method(
            self.client.service.deleteCallVariable,
            name=name,
            groupName=groupName
        )

    def getIVRScripts(self, script):
        """
        Gets Five9 IVR Scripts and returns it in SOAP envelope as provided by Five9:
        """
        scripts = self.process_method(
            self.client.service.getIVRScripts, namePattern=script
        )
        if scripts:
            for script in scripts:
                yield script

    def getDisposition(self, dispositionName) -> dict:
        """
        Gets Five9 disposition by name.
        Raise F9ServerFault if name does not exist.
        """
        obj = self.process_method(
            self.client.service.getDisposition,
            dispositionName=dispositionName
        )
        return serialize_object(obj, dict)

    def getDispositions(self, dispositionNamePattern: str = None) -> Iterator[dict]:
        """
        Search Five9 dispositions by name pattern or
        return all dispositions if no pattern provided.
        """
        objs = self.process_method(
            self.client.service.getDispositions,
            dispositionNamePattern=dispositionNamePattern
        )
        for obj in objs:
            yield serialize_object(obj, dict)

    def createDisposition(self, disposition) -> None:
        """ Creates Five9 disposition. No rv on successful create."""
        self.process_method(
            self.client.service.createDisposition,
            disposition=disposition
        )

    def modifyDisposition(self, disposition) -> None:
        """ Modifies existing Five9 disposition. No rv on successful modify."""
        self.process_method(
            self.client.service.modifyDisposition,
            disposition=disposition
        )

    def removeDisposition(self, dispositionName) -> None:
        """ Removes Five9 disposition. No rv on successful removal."""
        self.process_method(
            self.client.service.removeDisposition,
            dispositionName=dispositionName
        )
