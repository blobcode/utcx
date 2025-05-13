from flask import Flask, render_template, request, flash
import os

# Assuming pathing.py, course.py, and graph.py exist and are correct
from pathing import plan_course_schedule_cp, get_semester_type
from course import from_json_file
from graph import create_graph_from_courses

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for flashing messages

# Load course data and build graph (these should ideally be outside the request handling
# if they are large or slow, done here for simplicity as in the original)
try:
    merged_course_list = from_json_file("merged_courses.json")
    COURSE_GRAPH = create_graph_from_courses(merged_course_list)
    print("Course data loaded and graph built successfully.")
except FileNotFoundError:
    print("Error: merged_courses.json not found. Course data cannot be loaded.")
    COURSE_GRAPH = None  # Or handle this error appropriately


def get_available_courses(graph):
    """Helper function to get sorted list of non-logic course codes."""
    if graph is None:
        return []
    return sorted(
        [node for node, data in graph.nodes(data=True) if not data.get("logic", False)]
    )


@app.route("/", methods=["GET", "POST"])
def main_page():
    # Determine if it's an HTMX request
    is_htmx_request = request.headers.get("HX-Request") == "true"

    # Ensure graph is loaded before attempting to get courses
    if COURSE_GRAPH is None:
        flash("Course data could not be loaded. Planner is unavailable.", "error")
        # Render appropriate template based on request type
        if is_htmx_request:
            return render_template(
                "content.html",
                available_courses=[],
                status="Error: Data Load Failed",
            )
        else:
            return render_template(
                "index.html", available_courses=[], status="Error: Data Load Failed"
            )

    available_courses = get_available_courses(COURSE_GRAPH)

    # Initial context for GET or if POST fails validation early
    context = {
        "available_courses": available_courses,
        "status": None,
        "schedule": None,
        # Retain form values on POST - already handled by Jinja template
        "target_courses": request.form.get("target_courses", ""),
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
                # Render the partial template for HTMX request
                return render_template("content.html", **context)

            try:
                max_courses = int(max_courses_str)
                if max_courses <= 0:
                    raise ValueError("Max courses must be positive.")
            except ValueError as e:
                flash(
                    f"Invalid input for Max Courses per Semester: {e}. Please enter a positive whole number.",
                    "error",
                )
                # Render the partial template for HTMX request
                return render_template("content.html", **context)

            try:
                max_semesters = int(max_semesters_str)
                if max_semesters <= 0:
                    raise ValueError("Max semesters must be positive.")
            except ValueError as e:
                flash(
                    f"Invalid input for Max Semesters: {e}. Please enter a positive whole number.",
                    "error",
                )
                # Render the partial template for HTMX request
                return render_template("content.html", **context)

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

            # Prepare schedule for display if a schedule was returned
            display_schedule = {}
            if isinstance(
                schedule, dict
            ):  # Ensure schedule is a dictionary before processing
                for sem_index, courses in schedule.items():
                    year = sem_index // 2 + 1
                    # Ensure get_semester_type is correctly defined and imported
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
                # Sort semesters by index
                display_schedule = dict(sorted(display_schedule.items()))
                context["schedule"] = display_schedule
            elif schedule is not None:
                # Handle cases where schedule might be returned but not a dict (e.g., None, or an error indicator)
                print(
                    f"Planner did not return a schedule dictionary. Schedule type: {type(schedule)}"
                )

        except Exception as e:
            print(f"An error occurred during POST processing: {e}")
            # It's good practice to show a generic error to the user
            flash(
                f"An unexpected server error occurred during planning. Please try again.",
                "error",
            )
            context["status"] = "Error: Server Exception"  # Set error status in context
            # Log the detailed error on the server side
            import traceback

            traceback.print_exc()

        # For POST requests (which are HTMX initiated in this setup), render the partial template
        return render_template("content.html", **context)
    else:  # GET request (initial page load)
        # For GET requests, render the full template
        return render_template("index.html", **context)


# Add a simple check to run the app
if __name__ == "__main__":
    # Make sure merged_courses.json exists before running
    if not os.path.exists("merged_courses.json"):
        print(
            "Error: merged_courses.json not found. Please ensure it's in the same directory."
        )
        print("Cannot start the Flask application.")
    else:
        # In a production environment, you would use a production-ready WSGI server
        # For development, app.run() is fine.
        print(
            "Starting Flask development server. Ensure merged_courses.json is present."
        )
        # Consider adding debug=True during development for easier debugging
        # app.run(debug=True)
        app.run()
