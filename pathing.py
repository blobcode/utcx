import networkx as nx
from ortools.sat.python import cp_model
from course import Semester
import collections


def get_semester_type(semester_index: int) -> Semester:
    """Maps a semester index to Fall or Winter."""
    if semester_index % 2 == 0:
        return Semester.FALL
    else:
        return Semester.WINTER


def is_course_available(course_info: dict, semester_index: int) -> bool:
    """Checks if a course can be taken in a given semester index."""
    sessions = course_info.get("sessions", [])
    required_type = get_semester_type(semester_index)

    if course_info.get("length", 0.5) == 0.5:
        if required_type == Semester.FALL:
            return Semester.FALL in sessions
        else:
            return Semester.WINTER in sessions
    # Full year course (length 1.0) - Must start in fall
    elif course_info.get("length") == 1.0:
        return required_type == Semester.FALL


def plan_course_schedule_cp(
    g: nx.DiGraph,
    target_courses: list[str],
    max_courses_per_semester: int = 5,
    max_semesters: int = 8,
) -> tuple[str | None, dict | None]:
    """
    Plans a course schedule using Constraint Programming with two-phase optimization.
    Phase 1: Minimize total semesters.
    Phase 2: Minimize courses taken, given the minimum semesters.
    """
    try:
        for tc in target_courses:
            if tc not in g:
                print(f"Error: Target course {tc} not found in the provided graph.")
                return "Error: Target not in graph", None

        relevant_nodes = set()
        nodes_to_process = collections.deque(target_courses)
        processed_for_reachability = set()
        while nodes_to_process:
            current_node_id = nodes_to_process.popleft()
            if (
                current_node_id in processed_for_reachability
                or current_node_id not in g
            ):
                continue
            processed_for_reachability.add(current_node_id)
            relevant_nodes.add(current_node_id)
            for predecessor in g.predecessors(current_node_id):
                if predecessor not in processed_for_reachability:
                    nodes_to_process.append(predecessor)

        if not relevant_nodes:
            relevant_nodes.update(t for t in target_courses if t in g)
            if not relevant_nodes:
                return "Error: No relevant nodes", None

        course_nodes = {
            n for n in relevant_nodes if n in g and not g.nodes[n].get("logic", False)
        }
        logic_nodes = {
            n for n in relevant_nodes if n in g and g.nodes[n].get("logic", True)
        }

        model = cp_model.CpModel()

        takes = {}
        for c in course_nodes:
            for s in range(max_semesters):
                takes[c, s] = model.NewBoolVar(f"takes_{c}_s{s}")
        active = {}
        for ln in logic_nodes:
            for s in range(max_semesters + 1):
                active[ln, s] = model.NewBoolVar(f"active_{ln}_s{s}")

        for c in course_nodes:
            if c in target_courses:
                model.AddExactlyOne(takes[c, s] for s in range(max_semesters))
            else:
                model.AddAtMostOne(takes[c, s] for s in range(max_semesters))

        for c in course_nodes:
            if c not in g:
                continue
            course_info = g.nodes[c]
            course_length_semesters = 2 if course_info.get("length", 0.5) == 1.0 else 1
            for s in range(max_semesters):
                if not is_course_available(course_info, s):
                    model.Add(takes[c, s] == 0)
                if course_length_semesters == 2 and s == max_semesters - 1:
                    model.Add(takes[c, s] == 0)

        processed_edges = set()
        nodes_to_process_constraints = collections.deque(relevant_nodes)
        processed_nodes_constraints = set()

        while nodes_to_process_constraints:
            v = nodes_to_process_constraints.popleft()
            if v in processed_nodes_constraints:
                continue
            processed_nodes_constraints.add(v)

            for u in g.predecessors(v):
                if u not in relevant_nodes:
                    continue

                edge = (u, v)
                if edge in processed_edges:
                    continue
                processed_edges.add(edge)

                u_node_info = g.nodes[u]
                v_node_info = g.nodes[v]
                u_is_logic = u_node_info.get("logic", False)
                v_is_logic = v_node_info.get("logic", False)

                if not v_is_logic:
                    v_course = v
                    if not u_is_logic:
                        # (Add Course -> Course prereq constraint logic)
                        u_course = u
                        u_len = 2 if u_node_info.get("length", 0.5) == 1.0 else 1
                        for s_v in range(max_semesters):
                            sum_u_taken_valid_time = [
                                takes[u_course, s_u]
                                for s_u in range(s_v)
                                if s_u + u_len <= s_v
                            ]
                            if sum_u_taken_valid_time:
                                model.Add(
                                    sum(sum_u_taken_valid_time) >= 1
                                ).OnlyEnforceIf(takes[v_course, s_v])
                            else:
                                model.Add(takes[v_course, s_v] == 0)
                    else:  # u is Logic
                        u_logic = u
                        for s_v in range(max_semesters):
                            model.AddImplication(
                                takes[v_course, s_v], active[u_logic, s_v]
                            )
                else:  # v is Logic
                    v_logic = v
                    predecessors = [
                        p for p in g.predecessors(v_logic) if p in relevant_nodes
                    ]
                    v_type = v_node_info.get("type")
                    for s_v in range(max_semesters + 1):
                        if not predecessors:
                            model.Add(active[v_logic, s_v] == 1)
                            continue
                        preds_done_vars = []
                        for pred_id in predecessors:
                            pred_node_info = g.nodes[pred_id]
                            pred_is_logic = pred_node_info.get("logic", False)
                            if pred_is_logic:
                                preds_done_vars.append(active[pred_id, s_v])
                            else:
                                pred_course = pred_id
                                pred_len = (
                                    2 if pred_node_info.get("length", 0.5) == 1.0 else 1
                                )
                                pred_done_by_s = model.NewBoolVar(
                                    f"done_{pred_course}_by_s{s_v}"
                                )
                                possible_starts = [
                                    takes[pred_course, s_p]
                                    for s_p in range(s_v)
                                    if s_p + pred_len <= s_v
                                ]
                                if not possible_starts:
                                    model.Add(pred_done_by_s == 0)
                                else:
                                    model.AddMaxEquality(
                                        pred_done_by_s, possible_starts
                                    )
                                preds_done_vars.append(pred_done_by_s)

                        if v_type == "all":
                            model.AddBoolAnd(preds_done_vars).OnlyEnforceIf(
                                active[v_logic, s_v]
                            )
                            for pred_var in preds_done_vars:
                                model.AddImplication(
                                    pred_var.Not(), active[v_logic, s_v].Not()
                                )
                        elif v_type == "any":
                            model.AddBoolOr(preds_done_vars).OnlyEnforceIf(
                                active[v_logic, s_v]
                            )

                            for pred_var in preds_done_vars:
                                model.AddImplication(pred_var, active[v_logic, s_v])

                            all_preds_false_vars = [pv.Not() for pv in preds_done_vars]
                            model.AddBoolAnd(all_preds_false_vars).OnlyEnforceIf(
                                active[v_logic, s_v].Not()
                            )
                        else:
                            model.Add(active[v_logic, s_v] == 0)

        # constraint on max active courses
        for s in range(max_semesters):
            courses_active_in_s = []
            for c in course_nodes:
                courses_active_in_s.append(takes[c, s])
            if s > 0:
                for c in course_nodes:
                    if g.nodes[c].get("length", 0.5) == 1.0:
                        courses_active_in_s.append(takes[c, s - 1])
            model.Add(sum(courses_active_in_s) <= max_courses_per_semester)

        # minimize time
        max_finish_semester = model.NewIntVar(
            0, max_semesters - 1, "max_finish_semester"
        )

        for c in course_nodes:
            c_len = 2 if g.nodes[c].get("length", 0.5) == 1.0 else 1
            for s in range(max_semesters):
                finish_semester = s + c_len - 1
                if finish_semester < max_semesters:
                    model.Add(max_finish_semester >= finish_semester).OnlyEnforceIf(
                        takes[c, s]
                    )

        model.Minimize(max_finish_semester)

        print("Solving to minimize time...")
        solver = cp_model.CpSolver()
        # solver.parameters.log_search_progress = True # debug
        status1 = solver.Solve(model)

        optimal_time = -1  # no solution
        if status1 == cp_model.OPTIMAL or status1 == cp_model.FEASIBLE:
            try:
                optimal_time = int(solver.ObjectiveValue())
                print(f"Optimal time found: {optimal_time+1} semesters")
            except RuntimeError:
                print("Could not retrieve objective value after phase 1")

        elif status1 == cp_model.INFEASIBLE:
            print("Model infeasible (Phase 1).")
            return "Infeasible", None
        else:
            print(f"Solver failed: {status1}")
            return f"Unknown or Error ({status1})", None

        # optimal time
        if optimal_time < 0:
            print("Error: Could not determine optimal time.")
            return "Error: Phase 1 Failed", None
        model.Add(max_finish_semester <= optimal_time)

        # minimize total courses taken here
        total_courses_taken_vars = []
        for c in course_nodes:
            for s in range(max_semesters):
                total_courses_taken_vars.append(takes[c, s])

        model.Minimize(sum(total_courses_taken_vars))
        status2 = solver.Solve(model)

        # create schedule from model
        schedule_display = None
        status_str = "Unknown"  # Default

        if status2 == cp_model.OPTIMAL:
            status_str = "Optimal"  # Optimal for both time and course count
        elif status2 == cp_model.FEASIBLE:
            status_str = "Feasible"  # Optimal time, feasible course count (time limit?)
        elif status2 == cp_model.INFEASIBLE:
            print(
                "Error: Model became infeasible when minimizing courses. Check constraints/logic."
            )
            return "Error - Infeasible Phase 2", None
        else:
            status_str = f"Unknown or Error ({status2})"
            return status_str, None

        schedule_display = collections.defaultdict(list)
        actual_max_finish_sem = -1  # Recalculate based on final schedule
        if status2 == cp_model.OPTIMAL or status2 == cp_model.FEASIBLE:
            print(f"Solution Status (Phase 2 - Min Courses): {status_str}")
            try:
                min_courses_count = solver.ObjectiveValue()
                print(f"Minimum courses scheduled: {int(min_courses_count)}")
            except RuntimeError:
                print("Could not retrieve final course count objective.")

            temp_max_s = -1
            courses_found = []
            for s in range(max_semesters):
                for c in course_nodes:
                    if (c, s) in takes and solver.Value(takes[c, s]) == 1:
                        courses_found.append(c)
                        schedule_display[s].append(c)
                        course_info = g.nodes[c]
                        c_len_semesters = (
                            2 if course_info.get("length", 0.5) == 1.0 else 1
                        )
                        if c_len_semesters == 2 and s + 1 < max_semesters:
                            schedule_display[s + 1].append(c)
                        finish_semester = s + c_len_semesters - 1
                        temp_max_s = max(temp_max_s, finish_semester)

            actual_max_finish_sem = temp_max_s if temp_max_s != -1 else 0
            actual_max_finish_sem = max(0, actual_max_finish_sem)

            final_schedule_display = {
                sem: sorted(courses)
                for sem, courses in schedule_display.items()
                if sem <= actual_max_finish_sem and courses
            }

            print(final_schedule_display)

            return status_str, final_schedule_display
        else:  # Status was not Optimal or Feasible after phase 2
            return status_str, None

    except Exception as e:
        print(f"An error occurred during CP solving: {e}")
        return "Error", None
