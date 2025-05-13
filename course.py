"""
University of Toronto CSC111 Project 2 - U of T Course Planner Course Module
Copyright (c) 2025 Lucas Helme, Boyan Litchev, Thomas Sarrazin

Module Description
==================
Module provides access to the course, semester, and session datatypes
"""

from typing import Self, Optional
from enum import Enum
import re
import json
from filter_requisites import (
    FilterException,
    process_requisite,
    clean_string,
    prune_requisites_recursive,
)


class Semester(Enum):
    """
    Maps semesters to an interval representing them within the year.
    """

    SUMMER_1 = (0.1, 0.2)
    SUMMER_2 = (0.3, 0.4)
    SUMMER_BOTH = (0.1, 0.4)
    FALL = (0.5, 0.6)
    WINTER = (0.7, 0.8)
    FALL_WINTER = (0.5, 0.8)

    def next(self) -> Self:
        """Returns the next semester (in the order in which the semesters are defined above)"""
        cls = self.__class__
        members = list(cls)
        index = members.index(self) + 1
        if index >= len(members):
            index = 0
        return members[index]

    def __str__(self) -> str:
        """Returns the string corresponding to a semester"""
        match self:
            case Semester.SUMMER_1:
                return "Summer 1"
            case Semester.SUMMER_2:
                return "Summer 2"
            case Semester.SUMMER_BOTH:
                return "Summer 1&2"
            case Semester.FALL:
                return "Fall"
            case Semester.WINTER:
                return "Winter"
            case Semester.FALL_WINTER:
                return "Fall-Winter"
        return ""


def semester_from_str(semester: str) -> Semester:
    """Generates a semester from a string"""
    match semester:
        case "Summer 1":
            return Semester.SUMMER_1
        case "Summer 2":
            return Semester.SUMMER_2
        case "Summer 1&2":
            return Semester.SUMMER_BOTH
        case "Fall":
            return Semester.FALL
        case "Winter":
            return Semester.WINTER
        case "Fall-Winter":
            return Semester.FALL_WINTER
        case _:
            raise Exception(f'Invalid session input: "{semester}"')
    return ""


class Session:
    """
    A session in which a course can be offered at U of T

    Instance Attributes:
    - semester: one of "Fall", "Winter", "Fall-Winter", "Summer 1", "Summer 2", "Summer 1&2"
    - year: an integer representing what year the course can be taken in.
        this represents academic year, not calendar year, so for example a course in Winter 2026 should
        be represented as Winter 2025 here (this is to avoid issues with the Fall-Winter session not
        having a well-defined year)
    """

    semester: Semester
    year: int

    def __init__(self, session: Optional[tuple[str, int]] = None):
        if session is not None:
            self.semester = semester_from_str(session[0])
            self.year = session[1]

    def __iter__(self) -> Self:
        """Returns a copy of the object, to be used as an iterator"""
        result = Session()
        result.semester = self.semester
        result.year = self.year
        return result

    def __next__(self) -> Self:
        """Goes to the next available semester"""
        if self.semester == Semester.FALL_WINTER:
            self.year += 1
        self.semester = self.semester.next()
        return self

    def __str__(self) -> str:
        return f"({self.semester}, {self.year})"

    def end(self) -> float:
        """Returns a float corresponding to the end of a session"""
        return self.year + self.semester.value[1]

    def start(self) -> float:
        """Returns a float corresponding to the start of a session"""
        return self.year + self.semester.value[0]


def earliest_after(availability: list[Semester], session: Session) -> Session:
    """
    Computes the semester in 'availability' that ends earliest and is after session
    NOTE: A future goal is to make this consider courses that are available in alternate years
        , by changing availability to something other than a Semester
    """
    session_to_check = iter(session)
    # For loop to make sure we never go into an infinite loop if the semester is never available
    for _i in range(0, 24):
        session_to_check = next(session_to_check)
        if (
            session_to_check.semester in availability
            and session_to_check.start() > session.end()
        ):
            return session_to_check

    session_to_check.year = 2**15
    return session_to_check


class Course:
    """A course at U of T

    Instance Attributes:
    - notes: notes about this course generated while processing its data
    - name: The course code (ex. "CSC111")
    - title: The title of the course (ex. "Foundations of Computer Science II")
    - prereq_string: The string of prerequisites copied from ttb/academic calendar
    - prereq_list: A processed list of prerequisites
    - coreq_string: The string of corequisites copied from ttb/academic calendar
    - coreq_list: A processed list of corequisites
    - exclusions_list: A list of all exclusions for this course
    - sessions: The sessions in which this course was available
    """

    notes: str
    name: str
    title: str
    prereq_string: str
    prereq_list: list[list | str]
    coreq_string: str
    coreq_list: list[list | str]
    exclusions_list: list[str]
    sessions: dict[
        Semester, str
    ]  # A dictionary of semester : years in which the course was offered in that semester

    # note these methods are too short to justify docstrings
    def __init__(self):
        self.notes = ""
        self.prereq_list = ["all"]

    def get_notes(self):
        return self.notes

    def __str__(self) -> str:
        return self.name + ": " + self.title

    def set_name(self, name: str):
        self.name = name

    def get_name(self) -> str:
        return self.name

    def set_title(self, title: str):
        self.title = title

    def get_title(self) -> str:
        return self.title

    def reprocess_requisites(self) -> None:
        """
        Reprocesses the pre- and co-requisites of this course. Used so the processing algorithm
            can be modified without having to rescrape the academic calendar and query ttb again
        """
        self.notes = ""
        self.set_prerequisites(self.prereq_string)
        self.set_corequisites(self.coreq_string)

    def set_exclusions(self, exclusions: list):
        # NOTE: we currently exclude courses at UTM/UTSC
        self.exclusions_list = [
            excluded
            for excluded in exclusions
            if re.search("^[A-Z]{3}[0-9]{3}(H|Y)1$", excluded)
        ]

    def get_exclusions(self) -> list:
        return self.exclusions_list

    def set_prerequisites(self, prereq_string: str):
        """
        Generates a computer-friendly list of prerequisites, and stores it.
        NOTE: Auto-deletes prerequisite strings that have already been completed
        See `clean_string` and `process_course_list` for more info
        """
        self.prereq_string = prereq_string
        try:
            self.prereq_list, additional_notes = process_requisite(prereq_string)
            self.notes += additional_notes
        except FilterException:
            print(
                "Error reading in information from "
                + str(self)
                + ' ; could not parse "'
                + prereq_string
                + '".'
                + 'Best attempt was "'
                + clean_string(prereq_string)[0]
                + '". Notes: '
                + self.notes
            )

    def get_prerequisites(self) -> list:
        return self.prereq_list

    def get_prerequisites_raw(self) -> str:
        return self.prereq_string

    def set_corequisites(self, coreq_string: str):
        """
        Generates a computer-friendly list of corequisites, and stores it.
        NOTE: Auto-deletes corequisite strings that have already been completed
        See `clean_string` and `process_course_list` for more info
        """
        self.coreq_string = coreq_string
        try:
            self.coreq_list, additional_notes = process_requisite(coreq_string)
            self.notes += additional_notes
        except FilterException:
            print(
                "Error reading in information from "
                + str(self)
                + ' ; could not parse "'
                + coreq_string
                + '".'
                + 'Best attempt was "'
                + clean_string(coreq_string)[0]
                + '". Notes: '
                + self.notes
            )

    def get_corequisites(self) -> list:
        return self.coreq_list

    def prune_requisites(self, valid_courses: set[str]) -> None:
        """
        Prune all requisites recursively 
        (removes all requisites not in valid_courses, and also any logical nodes orphaned by this process)"""
        prune_requisites_recursive(self.prereq_list, valid_courses)
        prune_requisites_recursive(self.coreq_list, valid_courses)
        prune_requisites_recursive(self.exclusions_list, valid_courses)

    def __eq__(self, other: Self) -> bool:
        """
        Overloads the equality operator between courses.
        Two courses are considered equal if their name, title,
            prerequisite list, corequisite list, and exclusion list are the same, wherever a comparison is possible
            (the attribute is defined for both of the courses being compared).
        """
        # Both self and other must have a name and title that are equivalent to be considered equal courses
        if (
            "name" not in self.__dict__
            or "title" not in self.__dict__
            or "name" not in other.__dict__
            or "title" not in other.__dict__
        ):
            return False

        key_set = ["name", "title", "prereq_list", "coreq_list", "exclusions_list"]
        # Checks that every attribute that both courses have is the same
        for key in key_set:
            if key in self.__dict__ and key in other.__dict__:
                if self.__dict__[key] != other.__dict__[key]:
                    return False

        return True

    def set_sessions(self, sessions: dict[str, list[str]]):
        """
        Adds information about which sessions the course is offered in
        """
        self.sessions = {
            semester_from_str(key): value for key, value in sessions.items()
        }

    def get_semesters(self) -> list[Session]:
        """
        Returns a set of the semesters in which it's possible to take this course
        """
        return set(self.sessions.keys())

    def get_sessions(self) -> dict:
        return self.sessions

    def to_json(self) -> dict:
        """
        Converts each course into (a dictionary) of {attribute: value}
        """
        result = self.__dict__.copy()
        if "sessions" in result:
            sessions = result["sessions"]
            result["sessions"] = {str(key): value for key, value in sessions.items()}

        return result

    def from_json(self, info: dict):
        """
        Takes a dictionary, feeds all the data into this object
        """
        for key, value in info.items():
            if key == "sessions":
                self.set_sessions(value)
            else:
                self.__dict__[key] = value


def to_json_file(course_list: dict[str, Course], filename: str):
    """
    Takes a dictionary of the form {course name: course object},
    and writes all of its information to filename
    """

    json_course_list = {
        course: course_object.to_json() for course, course_object in course_list.items()
    }

    pretty_json = json.dumps(json_course_list, indent=2, sort_keys=False)

    with open(filename, "w") as file:
        file.write(pretty_json)


def from_json_file(filename: str) -> dict[str, Course]:
    """
    Takes a file with JSON data for all the courses,
    and turns it into a dictionary of courses
    """
    course_list = {}

    file = open(filename, "r")
    json_course_list = json.loads(file.read())
    file.close()

    for course in json_course_list:
        temp_course = Course()
        temp_course.from_json(json_course_list[course])
        course_list[course] = temp_course

    return course_list


if __name__ == "__main__":
    import python_ta
    import doctest

    doctest.testmod(
        verbose=True
    )  # run the tests and display all results (pass or fail)

    python_ta.check_all(
        config={
            "extra-imports": [],  # the names (strs) of imported modules
            "allowed-io": [],  # the names (strs) of functions that call print/open/input
            "max-line-length": 120,
        }
    )
