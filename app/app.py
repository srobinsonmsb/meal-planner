from flask import Flask, render_template, session, redirect, url_for
from db import get_connection, get_eater_ids, assign_meals
from scheduler import backfill_eater_schedule, assign_meal_names, assign_eater_names, meal_order, reroll_slot, eat_out_slot
from config import build_weekly_schedule, get_upcoming_monday, get_dates_for_week, backfill_schedule_with_dates

app = Flask(__name__)
app.secret_key = 'meal-planner-secret-key'

def generate_schedule():
    conn, cur = get_connection()
    eater_ids = get_eater_ids(cur)

    weekly_schedule = build_weekly_schedule()
    upcoming_monday = get_upcoming_monday()
    dates_per_day = get_dates_for_week(upcoming_monday)
    schedule_with_dates = backfill_schedule_with_dates(weekly_schedule, dates_per_day)

    eater_schedule = backfill_eater_schedule(eater_ids, schedule_with_dates)
    assign_meals(cur, eater_schedule, eater_ids)
    assign_meal_names(cur, eater_schedule)
    assign_eater_names(cur, eater_schedule)

    cur.close()
    conn.close()

    return eater_schedule, eater_ids

eater_schedule = None
eater_ids = None
slot_lookup = None


@app.route('/')
def home():
    global eater_schedule, eater_ids
    global slot_lookup
    slot_lookup = {}
    if eater_schedule is None:
        eater_schedule, eater_ids = generate_schedule()

    sorted_keys = sorted(eater_schedule.keys(), key=lambda x: (x[1], meal_order[x[2]], x[0]))
    schedule_list = []
    for index, (eater_id, date, meal_type) in enumerate(sorted_keys):
        slot = eater_schedule[(eater_id, date, meal_type)]
        schedule_list.append({
            'index': index + 1,
            'eater_name': slot.get('eater_name', 'Unknown'),
            'date': str(date),
            'meal_type': meal_type,
            'meal_name': slot.get('meal_name', 'No meal assigned'),
            'eat_out': slot.get('eat_out', False),
            'group': slot.get('group', False),
        })
        slot_lookup[index + 1] = (eater_id, date, meal_type)

    return render_template('index.html', schedule=schedule_list)


@app.route('/reroll/<int:slot_number>')
def reroll(slot_number):
    global eater_schedule, eater_ids, slot_lookup
    if eater_schedule is None:
        return redirect(url_for('home'))
    if slot_lookup is None:
        return redirect(url_for('home'))
    if slot_number in slot_lookup:
        conn, cur = get_connection()
        reroll_slot(cur, eater_schedule, slot_lookup, slot_number, eater_ids)
        assign_meal_names(cur, eater_schedule)
        cur.close()
        conn.close()
    return redirect(url_for('home'))

@app.route('/eat-out/<int:slot_number>')
def eat_out(slot_number):
    global eater_schedule, slot_lookup
    if eater_schedule is None:
        return redirect(url_for('home'))
    if slot_lookup is None:
        return redirect(url_for('home'))
    if slot_number in slot_lookup:
        eat_out_slot(eater_schedule, slot_lookup, slot_number)
    return redirect(url_for('home'))

app.run(host='0.0.0.0', port=5000, debug=True)