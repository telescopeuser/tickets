from . import routes
from forms import CreateEvent, DeleteEvents, AddTickets, RedeemTickets, CheckTickets
from flask import render_template, jsonify, redirect, url_for
import models
from mainApp import db, hashids
import sqlite3
import pandas as pd
import numpy as np


@routes.route('/')
@routes.route('/home')
def index():
    """Home summary page"""
    conn = sqlite3.connect("database.sqlite")
    # Use pandas to get dataframe and pivot
    df = pd.read_sql("SELECT * FROM events", conn)
    df = df.drop(columns=["ticket_id", "ticket_code"])
    x = df.pivot_table(index=["event_name", "event_date", "event_tickets"], values="redeemed", aggfunc=np.sum).reset_index()
    conn.close()
    return render_template('index.html', summary=np.array(x))


@routes.route('/events', methods=['GET', 'POST'])
def event_page():
    form_delete, form_add, form_create= DeleteEvents(), AddTickets(), CreateEvent()
    if form_delete.validate_on_submit():
        conn = sqlite3.connect("database.sqlite")
        event_name = form_delete.delete_event.data
        cur = conn.cursor()
        cur.execute(f"DELETE FROM events WHERE event_name = '{event_name}'")
        conn.commit()
        conn.close()
        print(f"Event deleted: {event_name}")
        return redirect(url_for("routes.event_page"))

    elif form_create.validate_on_submit():
        print("Creating a new event.")
        # Get entries
        conn = sqlite3.connect("database.sqlite")
        cur = conn.cursor()
        cur.execute("SELECT * FROM events")
        test = cur.fetchall()

        # If database is empty, start new entry
        if len(test) == 0:
            last_entry = 0
            start, end = last_entry, form_create.event_tickets.data
            print(start, end)
        else:
            last_entry = test[-1][3]
            start, end = last_entry + 1, form_create.event_tickets.data + last_entry + 1

        # Create new chunk of tickets
        for n in range(start, end):
            print(n)
            new_event = models.Events(
                event_name=form_create.event_name.data,
                event_date=form_create.event_date.data,
                event_tickets=form_create.event_tickets.data,
                ticket_id=n,
                ticket_code=hashids.encode(n),
                redeemed=False)
            db.session.add(new_event)
            db.session.commit()
            print(f"Entry number {n} created for {new_event}")

        conn.close()
        return redirect(url_for("routes.event_page"))

    elif form_add.validate_on_submit():
        conn = sqlite3.connect("database.sqlite")
        cur = conn.cursor()
        cur.execute("SELECT * FROM events")
        test = cur.fetchall()
        # If database is empty, start new entry
        if not test:
            last_entry = 0
            start, end = last_entry, form_add.new_tickets.data
        else:
            last_entry = test[-1][3]
            start, end = last_entry + 1, form_add.new_tickets.data + last_entry + 1

        df = pd.read_sql("SELECT * FROM events", conn)
        df_event = df[df["event_name"].isin([form_add.add_tickets_event.data])]

        if df_event.empty:
            print(f"Event name {form_add.add_tickets_event.data} does not exist! Can't add tickets...")
        else:
            en, ed = df_event["event_name"].values[0], df_event["event_date"].values[0]
            # new max amount of tickets
            et = df_event["event_tickets"].values[0] + form_add.new_tickets.data

            # Create new chunk of tickets
            for n in range(start, end):
                print(n)
                cur.execute(f"UPDATE events SET event_tickets = {et} WHERE event_name = '{en}';")
                conn.commit()
                cur.execute(f"INSERT INTO events(event_name, event_date, event_tickets, ticket_id, ticket_code, redeemed) VALUES('{en}', '{ed}', {et}, {n}, '{hashids.encode(n)}', {0});")
                conn.commit()

        conn.close()
        return redirect(url_for("routes.event_page"))

    else:
        conn = sqlite3.connect("database.sqlite")
        print("Displaying all tables.")
        cur = conn.cursor()
        cur.execute("SELECT * FROM events")
        ticket_table = cur.fetchall()
        conn.close()
        return render_template('events.html', form_delete=form_delete, form_create=form_create, form_add=form_add,
                               ticket_table=ticket_table)


@routes.route('/tickets', methods=['GET', "POST"])
def redeem_tickets():
    form_redeem, form_check = RedeemTickets(), CheckTickets()

    if form_redeem.validate_on_submit():
        conn = sqlite3.connect("database.sqlite")
        # Use pandas
        df_events = pd.read_sql("SELECT * FROM events", conn)
        ticket_to_redeem = df_events[df_events["ticket_code"].isin([form_redeem.ticket_code.data])]

        if ticket_to_redeem.empty:
            print("INVALID CODE")
            return render_template("statusPage.html", note="Ticket is invalid."), 404

        else:
            # Check if ticket has been redeemed
            if ticket_to_redeem["redeemed"].values[0] == 0:
                print(f"Redeeming ticket: {form_redeem.ticket_code.data}")
                cur = conn.cursor()
                cur.execute(f"UPDATE events SET redeemed = 1 WHERE ticket_code = '{form_redeem.ticket_code.data}';")
                conn.commit()
                conn.close()
                return render_template("statusPage.html", note="Ticket successfully redeemed."), 200

            else:
                print(f"Ticket: {form_redeem.ticket_code.data} already redeemed")
                return render_template("statusPage.html", note="Ticket already redeemed."), 410

    if form_check.validate_on_submit():
        conn = sqlite3.connect("database.sqlite")
        # Use pandas
        df_events = pd.read_sql("SELECT * FROM events", conn)
        ticket_to_redeem = df_events[df_events["ticket_code"].isin([form_check.ticket_check.data])]

        if ticket_to_redeem.empty:
            print("INVALID CODE")
            return render_template("statusPage.html",  note="Ticket is invalid."), 404
        else:
            # Check if ticket has been redeemed
            if ticket_to_redeem["redeemed"].values[0] == 0:
                print(f"Ticket not yet redeemed: {form_check.ticket_check.data}")
                return render_template("statusPage.html",  note="Ticket is available and not yet redeemed."), 200

            else:
                print(f"Ticket: {form_check.ticket_check.data} already redeemed")
                return render_template("statusPage.html",  note="Ticket already redeemed."), 410

    return render_template('tickets.html', form_redeem=form_redeem, form_check=form_check), 200


@routes.route('/tickets/<string:ticket_code>', methods=["GET"])
def ticket_status(ticket_code):
    conn = sqlite3.connect("database.sqlite")
    # Use pandas
    df_events = pd.read_sql("SELECT * FROM events", conn)
    ticket_to_redeem = df_events[df_events["ticket_code"].isin([ticket_code])]
    conn.close()
    if ticket_to_redeem.empty:
        print("INVALID CODE")
        return render_template("statusPage.html"), 404
    else:
        return jsonify(ticket_to_redeem.to_dict(orient="list"))

