from .base import CRUDEndpoint


class ContactCenterUsers(CRUDEndpoint):
    uri = "contact_center/users"

    def list_queues(self, user_id):
        url = self.url(f"{user_id}/queues")
        yield from self._paged_get(url, "queues")

    def list_skills(self, user_id, **params):
        url = self.url(f"{user_id}/skills")
        yield from self._paged_get(url, "skills", params)

    def assign_skills(self, user_id, payload) -> None:
        url = self.url(f"{user_id}/skills")
        self.session.post(url, json=payload)

    def unassign_skill(self, user_id, skill_id) -> None:
        url = self.url(f"{user_id}/skills/{skill_id}")
        resp = self.session.delete(url)


class ContactCenterSkills(CRUDEndpoint):
    uri = "contact_center/skills"

    def list_users(self, skill_id):
        url = self.url(f"{skill_id}/users")
        yield from self._paged_get(url, "users")


class ContactCenterSkillCategories(CRUDEndpoint):
    uri = "contact_center/skills/categories"
    list_key = "skill_categories"


class ContactCenterQueues(CRUDEndpoint):
    uri = "contact_center/queues"

    def list_agents(self, queue_id):
        url = self.url(f"{queue_id}/agents")
        yield from self._paged_get(url, "agents")

    def assign_agents(self, queue_id, payload) -> dict:
        url = self.url(f"{queue_id}/agents")
        resp = self.session.post(url, json=payload)
        return resp.json()

    def unassign_agent(self, queue_id, user_id) -> None:
        url = self.url(f"{queue_id}/agents/{user_id}")
        resp = self.session.delete(url)

    def list_supervisors(self, queue_id):
        url = self.url(f"{queue_id}/supervisors")
        yield from self._paged_get(url, "supervisors")

    def assign_supervisors(self, queue_id, payload) -> dict:
        url = self.url(f"{queue_id}/supervisors")
        resp = self.session.post(url, json=payload)
        return resp.json()

    def unassign_supervisor(self, queue_id, user_id) -> None:
        url = self.url(f"{queue_id}/supervisors/{user_id}")
        resp = self.session.delete(url)

    def list_dispositions(self, queue_id):
        url = self.url(f"{queue_id}/dispositions")
        yield from self._paged_get(url, "dispositions")

    def assign_dispositions(self, queue_id, payload) -> dict:
        url = self.url(f"{queue_id}/dispositions")
        resp = self.session.post(url, json=payload)
        return resp.json()

    def unassign_disposition(self, queue_id, disposition_id) -> None:
        url = self.url(f"{queue_id}/dispositions/{disposition_id}")
        resp = self.session.delete(url)

    # Convenience methods to avoid duplicating if/else
    # logic all over service modules
    def list_users(self, queue_type, queue_id):
        if "agent" in queue_type:
            return self.list_agents(queue_id)
        else:
            return self.list_supervisors(queue_id)

    def assign_users(self, queue_type, queue_id, payload):
        if "agent" in queue_type:
            return self.assign_agents(queue_id, payload)
        else:
            return self.assign_supervisors(queue_id, payload)

    def unassign_user(self, queue_type, queue_id, user_id):
        if "agent" in queue_type:
            self.unassign_agent(queue_id, user_id)
        else:
            self.unassign_supervisor(queue_id, user_id)


class ContactCenterDispositions(CRUDEndpoint):
    uri = "contact_center/dispositions"


class ContactCenterDispositionSets(CRUDEndpoint):
    uri = "contact_center/dispositions/sets"
    list_key = "disposition_sets"


class ContactCenterRoles(CRUDEndpoint):
    uri = "contact_center/roles"
