from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional
from collections.abc import Callable

import pytz
from bs4 import BeautifulSoup
from dateutil.parser import parse

from gradescope_api.errors import GradescopeAPIError, check_response
from gradescope_api.submission import GradescopeSubmission

if TYPE_CHECKING:
    from gradescope_api.client import GradescopeClient
    from gradescope_api.course import GradescopeCourse

GRADESCOPE_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class GradescopeAssignment:
    def __init__(self, _client: GradescopeClient, _course: GradescopeCourse, assignment_id: str, assignment_name: Optional[str] = None) -> None:
        self._client = _client
        self._course = _course
        self.assignment_id = assignment_id
        self.assignment_name = assignment_name

    def get_url(self) -> str:
        return self._course.get_url() + f"/assignments/{self.assignment_id}"

    def get_name(self) -> str:
        if self.assignment_name is None:
            course_id = self._course.course_id
            assignment_id = self.assignment_id
            response = self._client.session.get(
                f"https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}"
            )
            check_response(response, "could not load assignment")
            soup = BeautifulSoup(response.content, "html.parser")
            self.assignment_name = soup.find("h2", {"class" : "sidebar--title"})["title"]
        return self.assignment_name
        
    def get_latest_submission(self, student: GradescopeStudent) -> Optional[GradescopeSubmission]:
        """
        Get the latest submission for this assignment given a GradescopeStudent
        """
        course_id = self._course.course_id
        assignment_id = self.assignment_id
        response = self._client.session.get(
            f"https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}/submissions", timeout=20
        )
        check_response(response, "could not load assignment")
        soup = BeautifulSoup(response.content, "html.parser")
        rows = [r.find("a") for r in soup.find_all("td", class_="table--primaryLink")]
        submission_id = None
        for row in rows:
            if row.text == student.full_name:
                submission_id = row["href"].split('/')[-1]
                break

        if submission_id is None:
            return None
        return GradescopeSubmission(
            self._client,
            course_id,
            self,
            student,
            submission_id
        )
        
        # self._client.start_driver()
        # self._client.driver.get(f"https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}/submissions")

    def get_latest_submissions(
        self,
        where: Optional[
            Union[List[GradescopeStudent],
                  Callable[[GradescopeSubmission], bool]
        ]]=lambda x: True
    ) -> List[GradescopeSubmission]:
        """
        Get all the latest submissions for this assignment
        """            
        course_id = self._course.course_id
        assignment_id = self.assignment_id
        response = self._client.session.get(
            f"https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}/submissions", timeout=20
        )
        check_response(response, "could not load assignment")
        roster = self._course.get_roster()
        soup = BeautifulSoup(response.content, "html.parser")
        rows = [r.find("a") for r in soup.find_all("td", class_="table--primaryLink")]
        submissions = []
        for row in rows:
            submission_id = row["href"].split('/')[-1]
            student = next(filter(lambda x: x.full_name == row.text, roster))
            submission = GradescopeSubmission(
                self._client,
                course_id,
                self,
                student,
                submission_id
            )
            submissions.append(submission)

        if callable(where):
            filter_fn = where
        elif isinstance(where, list):
            valid_ids = set(student.user_id for student in where)
            filter_fn = lambda x: x._student.user_id in valid_ids
        else:
            raise ValueError('"where" is not a list of GradescopeStudent objects or function on GradescopeSubmission objects.')
            
        return list(filter(filter_fn, submissions))

    def get_all_submissions(
        self,
        where: Optional[Callable[[GradescopeSubmission], bool]]=lambda x: True,
        where_latest: Optional[
            Union[List[GradescopeStudent],
                  Callable[[GradescopeSubmission], bool]
        ]]=lambda x: True
    ) -> List[GradescopeSubmission]:
        """
        Get every submission for this assignment.
        """
        latest_subs = self.get_latest_submissions(where_latest)
        all_subs = []
        for latest_sub in latest_subs:
            response = self._client.session.get(f"{latest_sub.get_url()}.json?content=react&only_keys[]=past_submissions")
            check_response(response, "could not load past submissions")
            past_sub_data = json.loads(response.content)['past_submissions']
            for past_data in past_sub_data:
                sub = GradescopeSubmission(
                    self._client,
                    self._course.course_id,
                    self,
                    latest_sub._student,
                    past_data['id']
                )
                if where(sub):
                    all_subs.append(sub)
            
        return all_subs

    def apply_extension(self, email: str, num_days: int, num_hours: Optional[int] = 0):
        """
        A new method to apply an extension to a Gradescope assignment, given an email and a number of days.
        """
        # First, fetch the extensions page for the assignment, which contains a student roster as well as
        # the due date (and hard due date) for the assignment.
        course_id = self._course.course_id
        assignment_id = self.assignment_id
        response = self._client.session.get(
            f"https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}/extensions", timeout=20
        )
        check_response(response, "could not load assignment")

        # Once we fetch the page, parse out the data (students + due dates)
        soup = BeautifulSoup(response.content, "html.parser")
        props = soup.find(
            "li", {"data-react-class": "AddExtension"})["data-react-props"]
        data = json.loads(props)
        
        students = {row["email"]: row["id"]
                    for row in data.get("students", [])}
        user_id = students.get(email)
        if not user_id:
            raise GradescopeAPIError("student email not found")

        # A helper method to transform the date
        def transform_date(datestr: str, timezone_identifier: str):
            dt = pytz.timezone(timezone_identifier).localize(parse(datestr))
            dt = dt + timedelta(days=num_days, hours=num_hours)
            return dt.astimezone(pytz.utc)

        assignment = data["assignment"]
        tz_id = data["timezone"]["identifier"]
        new_due_date = transform_date(assignment["due_date"], tz_id)

        if assignment["hard_due_date"]:
            new_hard_due_date = transform_date(assignment["hard_due_date"], tz_id)

        # Make the post request to create the extension
        url = self.get_url() + "/extensions"
        headers = {
            "Host": "www.gradescope.com",
            "Origin": "https://www.gradescope.com",
            "Referer": url,
            "X-CSRF-Token": self._client._get_token(url, meta="csrf-token"),
        }
        payload = {
            "override": {
                "user_id": user_id,
                "settings": {
                    "due_date": {"type": "absolute", "value": new_due_date.strftime(GRADESCOPE_DATETIME_FORMAT)}
                },
            }
        }

        if assignment["hard_due_date"]:
            payload["override"]["settings"]["hard_due_date"] = {
                "type": "absolute",
                        "value": new_hard_due_date.strftime(GRADESCOPE_DATETIME_FORMAT),
            }

        response = self._client.session.post(
            url, headers=headers, json=payload, timeout=20)
        check_response(response, "creating an extension failed")

    # deprecated
    def create_extension(self, user_id: str, due_date: datetime, hard_due_date: Optional[datetime] = None):
        """
        Create an extension for a student for this particular assignment. If a hard due date is not provided,
        the hard due date will be set to the provided due date. This behavior is temporary and should be changed
        to be the later of the current hard due date and the provided due date.
        """
        if hard_due_date:
            assert hard_due_date >= due_date

        url = self.get_url() + "/extensions"
        headers = {
            "Host": "www.gradescope.com",
            "Origin": "https://www.gradescope.com",
            "Referer": url,
            "X-CSRF-Token": self._client._get_token(url, meta="csrf-token"),
        }
        payload = {
            "override": {
                "user_id": user_id,
                "settings": {
                    "due_date": {"type": "absolute", "value": due_date.strftime(GRADESCOPE_DATETIME_FORMAT)},
                    "hard_due_date": {
                        "type": "absolute",
                        "value": (hard_due_date or due_date).strftime(GRADESCOPE_DATETIME_FORMAT),
                    },
                },
            }
        }

        response = self._client.session.post(
            url, headers=headers, json=payload, timeout=20)
        check_response(response, "creating an extension failed")
