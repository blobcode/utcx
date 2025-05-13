from flask import Flask, render_template, request, flash, redirect, url_for
import os

from pathing import plan_course_schedule_cp, get_semester_type
from course import from_json_file
from graph import create_graph_from_courses

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for flashing messages

merged_course_list = from_json_file("merged_courses.json")
COURSE_GRAPH = create_graph_from_courses(merged_course_list)


def get_available_courses(graph):
    """Helper function to get sorted list of non-logic course codes."""
    return sorted(
        [node for node, data in graph.nodes(data=True) if not data.get("logic", False)]
    )


@app.route("/", methods=["GET", "POST"])
def main_page():
    available_courses = get_available_courses(COURSE_GRAPH)
    context = {
        "available_courses": available_courses,
        "status": None,
        "schedule": None,
        "target_courses": request.form.get(
            "target_courses", ""
        ),  # Keep form values on POST
        "max_courses": request.form.get("max_courses", "5"),
        "max_semesters": request.form.get("max_semesters", "8"),
    }

    if request.method == "POST":
        try:
            target_courses_str = context["target_courses"]
            max_courses_str = context["max_courses"]
            max_semesters_str = context["max_semesters"]

            # Basic Validation and Type Conversion
            target_courses = [
                c.strip().upper() for c in target_courses_str.split(",") if c.strip()
            ]
            if not target_courses:
                flash("Please enter at least one target course code.", "error")
                return render_template("index.html", **context)  # Re-render with flash

            try:
                max_courses = int(max_courses_str)
                if max_courses <= 0:
                    raise ValueError("Max courses must be positive.")
            except ValueError as e:
                flash(
                    f"Invalid input for Max Courses per Semester: {e}. Please enter a positive whole number.",
                    "error",
                )
                return render_template("index.html", **context)  # Re-render with flash

            try:
                max_semesters = int(max_semesters_str)
                if max_semesters <= 0:
                    raise ValueError("Max semesters must be positive.")
            except ValueError as e:
                flash(
                    f"Invalid input for Max Semesters: {e}. Please enter a positive whole number.",
                    "error",
                )
                return render_template("index.html", **context)  # Re-render with flash

            print(
                f"Calling planner with targets: {target_courses}, max_c: {max_courses}, max_s: {max_semesters}"
            )
            status, schedule = plan_course_schedule_cp(
                COURSE_GRAPH,
                target_courses,
                max_courses_per_semester=max_courses,
                max_semesters=max_semesters,
            )
            print(f"Planner returned status: {status}")
            context["status"] = status

            # Prepare schedule for display
            display_schedule = {}
            if isinstance(schedule, dict):
                for sem_index, courses in schedule.items():
                    year = sem_index // 2 + 1
                    sem_type = get_semester_type(sem_index)
                    sem_name = f"Year {year} {sem_type.name.capitalize()}"
                    courses_with_names = []
                    for code in courses:
                        node_data = COURSE_GRAPH.nodes.get(code, {})
                        name = node_data.get("name", "")
                        courses_with_names.append(
                            f"{code}{f': {name}' if name else ''}"
                        )
                    display_schedule[sem_index] = {
                        "name": sem_name,
                        "courses": sorted(courses_with_names),
                    }
                display_schedule = dict(sorted(display_schedule.items()))
                context["schedule"] = display_schedule

        except Exception as e:
            print(f"An error occurred during POST processing: {e}")
            flash(f"An unexpected server error occurred during planning: {e}", "error")
            context["status"] = "Error: Server Exception"  # Set error status in context
    return render_template("index.html", **context)
