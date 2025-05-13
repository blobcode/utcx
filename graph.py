"""
University of Toronto CSC111 Project 2 - U of T Course Planner Graph Generator
Copyright (c) 2025 Lucas Helme, Boyan Litchev, Thomas Sarrazin

Module Description
==================
This module is a helper module for main.py which generates a NetworkX Directed Acyclic Graph (DAG) depending on the
input in the Course bar in the pyqtgraph interactable window. The graph vertices and edges are determined using the
course JSON file and parsing the requisites list of the desired course.

This module should be used specifically in the U of T Course Planner in main.py and not as a standalone module.
"""

import uuid
import networkx as nx
from course import Course, Semester


def parse_requisite_list(
    req_list: list, course_id: str, g: nx.DiGraph, data: dict[str, Course]
) -> None:
    """
    Parse a requisite list and add logic nodes/edges to the graph. Mutates g.

    Representation Invariants:
        - req_list is a subset of g and data
    """
    if not req_list or len(req_list) < 2:
        return

    op_type = req_list[0]  # 'all' or 'any'
    children = req_list[1:]

    if len(children) == 1:
        child = children[0]
        if isinstance(child, list):
            parse_requisite_list(child, course_id, g, data)
        else:
            if child in data:  # Only add node if it exists in data
                if not g.has_node(child):
                    g.add_node(child, logic=False)
                g.add_edge(child, course_id)
    else:
        # Create a virtual logic node
        v_id = str(uuid.uuid4().hex[:8])
        g.add_node(v_id, type=op_type, logic=True, color=(255, 255, 255))
        g.add_edge(v_id, course_id)

        for item in children:
            if isinstance(item, list):
                parse_requisite_list(item, v_id, g, data)
            else:
                if item in data:  # Only add node if it exists in data
                    if not g.has_node(item):
                        g.add_node(item, logic=False, color=(255, 255, 255))
                    g.add_edge(item, v_id)


def create_graph_from_courses(course_list: dict[str, Course]) -> nx.DiGraph:
    """
    Create a NetworkX DiGraph from the course data and return it.

    Representation Invariants:
        - course_list is correctly formatted
        - all semesters are valid
    """
    # Create directed graph
    g = nx.DiGraph()

    allowed_sems = (Semester.FALL, Semester.WINTER, Semester.FALL_WINTER)

    # Process each course
    for name, course in course_list.items():
        length = 0.5
        if name[-2] == "Y":
            length = 1.0

        g.add_node(
            name,
            title=course.get_title(),
            sessions=[
                semester
                for semester in course.get_semesters()
                if semester in allowed_sems
            ],
            length=length,
            logic=False,
        )

        # Makes sure the prerequisite list is nonempty
        if course.get_prerequisites():
            parse_requisite_list(course.get_prerequisites(), name, g, course_list)

    return g
