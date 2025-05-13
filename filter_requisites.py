"""
University of Toronto CSC111 Project 2 - U of T Course Planner filter_requisites Module
Copyright (c) 2025 Lucas Helme, Boyan Litchev, Thomas Sarrazin

Module Description
==================
Module provides access to functions used to turn a pre- or co-requisite in string format into
a list that can be processed by the graph generator"""

import re

# A list of strings that are valid requisites
VALID_REQUISITES = {
    r"High school level calculus": "High school calculus",
    r"High school level algebra\.?": "High school algebra",
    r"Grade 12 Mathematics": "Grade 12 math",
    r"equivalent programming experience": "Equivalent programming experience",
    r"proficiency in C or C\+\+": "C/C++ proficiency",
    r"(Any )?0\.5 credit in CSC": "half a credit in CSC",
    r"MCV4U Calculus & Vectors": "High school calculus",
    r"MCB4U Functions & Calculus": "High school calculus",
    r"MCB4U Calculus": "High school calculus",
    r"SPH4U Physics": "High school physics",
    r"SCH4U Chemistry": "High school chemistry",
    r"ICS4U Computer Science": "High school computer science",
    r"SES4U Earth and Space Science": "High school Earth and Space science",
    r"First-year Calculus": "First-year Calculus",
}

# Strings that will cause a note to be generated in clear_patterns
NOTEABLE = {
    r"[pP]ermission of the Associate Chair for Undergraduate Studies and of the prospective supervisor": "Need undergrad chair permission",
    r"Permission of Undergraduate Co-ordinator and Supervisor": "Need undergrad coordinator/supervisor permission",
    r"Consult the Physics Associate Chair \(Undergraduate Studies\)": "Need undergrad chair permission",
    r"Possible additional topic-specific prerequisites": "Possible topic-specific prereqs",
    r"\((\s)?[A-Z0-9]{8} can be taken concurrently\)": ".Note: ",
    # Some number of credits at at least some level in some department
    r"[0-9].[0-9] credits with a CGPA of at least [0-9].[0-9], and": ".Need ",
    r"(and at least )?[0-9]\.[0-9] [A-Z]{3}/[A-Z]{3} credit(s)? at the [0-9]00(/[0-9]00)?(\+)?(-|\s)level": ".Prereq: ",
    r"[0-9]\.[0-9] [A-Z]{3}/[A-Z]{3} credit(s)? at the 100, 200 and 300-level": ".Prereq: ",
    r"[0-9]\.[0-9] credits of [0-9]00\+ level [A-Z]{3} courses": ".Prereq: ",
    r"[0-9]\.[0-9] credits of [0-9]00\+ level CSC courses": ".Prereq: ",
    r"(and )?(at least )?[0-9]\.[0-9] credit(s)? (in [A-Z]{3} )?at the [0-9]00(-|\+ )level( or higher)?( in [A-Z]{3}/[A-Z]{3})?": ".Prereq: ",
    r"(Any )?[0-9]\.[0-9] credit(s)? in [A-Z]{3}": ".Prereq: ",
    r"(A minimum of )?(Completion of )?([aA]t least )?[0-9]+\.[0-9] credits": ".Prereq: ",
    # Other exemptions
    r" or (by )?permission of (the )?instructor": "Can take with instructor permission",
    r"Students who do not meet these prerequisites are encouraged to contact the Department": " can contact department for prereq exemptions",
    r"[Nn]ote:\s+[A-Z0-9]{8}\s+may be taken as a co-requisite": ".",
    r"\([Nn]ote:[A-Z0-9\s\(\),/;]*(are )?very strongly recommended(\.)?\)": ".",
    r"\([A-Za-z\s\.:]+\)": ".",
    r"equivalent mathematical background": "can skip some prereqs with enough math experience",
    r"\*Note\: the corequisite may be completed either concurrently or in advance": ".",
    r"\(?Note.*": ".",
    r"proficiency in C, C\+\+, or Fortran": ".Note: can skip stuff with",
    r"or equivalent (AST )?readings(;|,) consult the instructor": ".Note: can skip stuff with",
    r"and exposure to PDEs": "Might need PDE exposure",
}

# A list of strings that will be deleted in clear_patterns
TO_DELETE = [
    r"Corequisite: ",
    r"Prerequisite: ",
    r"Exclusion(s)?: ",
    r"Any CSC 0\.5 credit, and balloting",
    r"For FASE students, [A-Z0-9,\(\)\\\s]*",
    r"No prior experience with physical science will be required, but familiarity with Grade 10 mathematics will be assumed",
    r"[0-9].[0-9] [A-Z]{3} credit at the 100-level",
    # Deletes minimum GPA requirements
    r"[mM]inimum GPA( of)? [0-9]\.[0-9] (for|of|in) [A-Z]{3} and [A-Z]{3} courses",
    r"Minimum GPA of [0-9]\.[0-9]",
    # Removes all kinds of expressions that specify a minimum grade
    r"with a minimum mark of (at least )?[0-9][0-9](%)?",
    r"minimum (grade )?(of )?[0-9][0-9]%( in)?",
    r"[0-9][0-9]% or higher( in)?",
    r"[0-9][0-9]%( minimum)?( in )?( )?",
    # Removes recommended courses (I only care about required ones...)
    r"\([.]* recommended\)",
    r"recommended",
    r"[A-Z0-9]{6}[HY][35]",  # removes non-st.george courses
    # r"\s", #at the end, deletes whitespaces
    r"\.",  # and punctuation (presumably left by previous sentences)
    r"\u200b",  # whitespace character
    r"\u00a0",
    r"\xa0",
    r"None",
    r"\(\)",  # deletes stray pairs of parentheses
    r"\[\]",
]


class FilterException(Exception):
    pass


def process_requisite(requisite_string: str) -> tuple[list, str]:
    """
    Returns a processed list, and error messages if any occur
    """
    cleaned_string, notes = clean_string(requisite_string)
    processed_list = process_course_list(cleaned_string)
    return (processed_list, notes)


def process_course_list(clean_str: str) -> list:
    """
    Turns a clean string into a list of courses.
    If you have to take all of a list of courses, the 0th index of the list is "all",
    and if any course from a series of courses will suffice, the 0th index is "any"
    """

    course_list = ["all"]
    process_course_list_recursive(course_list, clean_str)

    # If the list has exactly one element that's a list, extract it and return that instead
    if len(course_list) == 2 and type(course_list[1]) == list:
        course_list = course_list[1]

    return course_list


def process_course_list_recursive(course_list: list, remaining_str: str) -> str:
    """A parametarized version of the previous function"""
    if re.search(r"[\(\),/\[\];]", remaining_str) is None:
        if remaining_str != "":
            course_list.append(remaining_str)
        return ""

    idx = re.search(r"[\(\),/\[\];]", remaining_str).start()

    # Finds the current course and delimiter
    course = remaining_str[:idx]
    delimiter = remaining_str[idx]
    remaining_str = remaining_str[idx + 1 :]

    if delimiter in ("(", "[") and course != "":
        # We should never have a course followed by a parentheses without a delimiter
        raise FilterException("Error reading information from string")

    if course != "":
        course_list.append(course)

    # If we need to create a new branch, we do so
    if delimiter in (";", ",") and course_list[0] == "any":
        return ";" + remaining_str

    elif delimiter == "/" and course_list[0] == "all":
        new_list = ["any"]

        if len(course_list) > 1:
            # The last element of course_list should have been inside this all statement
            new_list.append(course_list.pop())

        remaining_str = process_course_list_recursive(new_list, remaining_str)

        if len(new_list) == 2:
            # If only one item was inside the parenthases, we add it to this list
            course_list.append(new_list[1])
        elif len(new_list) > 2:
            course_list.append(new_list)

        if len(remaining_str) > 0 and remaining_str[0] == ")":
            return remaining_str
    elif delimiter in ("(", "["):
        new_list = ["all"]
        remaining_str = process_course_list_recursive(new_list, remaining_str)

        if len(remaining_str) == 0 or remaining_str[0] != ")":
            raise FilterException("Error reading information from string")
        else:
            remaining_str = remaining_str[1:]

        if len(new_list) == 2:
            # If only one item was inside the parentheses, we add it to this list
            course_list.append(new_list[1])
        elif len(new_list) > 2:
            # If there was more than 1 item inside the parentheses, we add the
            # list from the parentheses to our current list
            course_list.append(new_list)

    elif delimiter in (")", "]"):
        return ")" + remaining_str

    # Once we return out of a sublist, we continue with the recursion
    return process_course_list_recursive(course_list, remaining_str)


def clean_string(messy_str: str) -> tuple[str, str]:
    """
    Returns a version of the string that contains only courses (or elements of VALID_REQUISITES),
        separated by the characters "(),/;"

    So, text fragments such as "60% or higher in" are removed. If an unrecognized string is
    contained, it is added to the notes.
    """
    result = ""

    remaining_str, notes = clear_patterns(messy_str)
    uncleanable = False

    while len(remaining_str) > 0:
        if re.search(r"[\(\),/\[\];]", remaining_str) is not None:
            idx = re.search(r"[\(\),/\[\];]", remaining_str).start()
        else:
            idx = len(remaining_str)

        portion = remaining_str[:idx].strip()

        valid, course = is_valid_course(portion)
        if valid:
            result += course
        elif portion != "":
            notes += 'Bad portion: "' + portion + '", '
            uncleanable = True

        # If there was an ending delimiter, add it back
        if idx < len(remaining_str):
            result += remaining_str[idx]

        remaining_str = remaining_str[idx + 1 :]

    if uncleanable:
        notes += 'Uncleanable string: "' + messy_str + '"'

    return (result, notes)


def clear_patterns(messy_str: str) -> tuple[str, str]:
    """
    Modifies expressions that matche the regexes in NOTABLE, COMPLETED_STRINGS, or TO_DELETE
    Expressions in `to_delete` are deleted
    Expressions in `notable` are removed, and a note is added to notes
    """
    notes = ""
    for pattern, message in NOTEABLE.items():
        if re.search(pattern, messy_str) is not None:
            if message[0] == ".":
                notes += message[1:] + " ".join(
                    [x.group() for x in re.finditer(pattern, messy_str)]
                )
            else:
                notes += "Note: " + message

            messy_str = re.sub(pattern, "", messy_str)

    for pattern in TO_DELETE:
        messy_str = re.sub(pattern, "", messy_str)

    messy_str = re.sub(r"and one of", ";", messy_str)
    messy_str = re.sub(r"and", ";", messy_str)
    messy_str = re.sub(r"AND", ";", messy_str)
    messy_str = re.sub(r"or", "/", messy_str)
    messy_str = re.sub(r"OR", "/", messy_str)

    return (messy_str, notes)


def is_valid_course(test_string: str) -> tuple[bool, str]:
    """
    Checks if a course code matches the format for a valid requisite
    NOTE: currently only marks St.George courses as valid
    A requisite is valid if it
        - is a St.George undergrad course
        - OR, is a St.George graduate course
        - is the string "completed"
        - is in VALID_REQUISITES
    """
    # St.Geroge course
    if (
        len(test_string) == 8
        and test_string[0:3].isalpha()
        and test_string[3:6].isnumeric()
        and test_string[6] in ("H", "Y")
        and test_string[7] == "1"
    ):
        return (True, test_string)

    #
    if (
        len(test_string) == 8
        and test_string[0:3].isalpha()
        and test_string[3:7].isnumeric()
        and test_string[7] in ("H", "Y")
    ):
        return (True, test_string)

    if test_string == "completed":
        return (True, "completed")

    for requisite, simplified_version in VALID_REQUISITES.items():
        if re.fullmatch(requisite, test_string):
            if simplified_version == ".":
                return (True, test_string)
            else:
                return (True, simplified_version)
    return (False, "")


def prune_requisites_recursive(
    requisites: list[str | list], valid_courses: set[str]
) -> None:
    """
    Removes all requisites from 'requisites' that are not in valid_courses or VALID_REQUISITES
    Also removes logical nodes orphaned by this process.
    """
    idx = 0
    while len(requisites) > idx:
        requisite = requisites[idx]
        if requisite in ("any", "all"):
            idx += 1
        elif type(requisite) == str:
            if requisite in VALID_REQUISITES or requisite in valid_courses:
                idx += 1
            else:
                requisites.pop(idx)
        else:
            prune_requisites_recursive(requisite, valid_courses)
            # If only an any/all node is left
            if len(requisite) <= 1:
                requisites.pop(idx)
            else:
                idx += 1
