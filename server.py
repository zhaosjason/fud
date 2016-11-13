#!/usr/bin/env python2.7

"""
Columbia W4111 Intro to databases
Example webserver

To run locally

    python server.py

Go to http://localhost:8111 in your browser


A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""

import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

with open("password.txt", "r") as f:
  passwd = f.readline()

DATABASEURI = "postgresql://ss4924:" + passwd.strip() + "@104.196.175.120/postgres"
engine = create_engine(DATABASEURI)


@app.before_request
def before_request():
  """
  This function is run at the beginning of every web request 
  (every time you enter an address in the web browser).
  We use it to setup a database connection that can be used throughout the request

  The variable g is globally accessible
  """
  try:
    g.conn = engine.connect()
  except:
    print "uh oh, problem connecting to database"
    import traceback; traceback.print_exc()
    g.conn = None

@app.teardown_request
def teardown_request(exception):
  """
  At the end of the web request, this makes sure to close the database connection.
  If you don't the database could run out of memory!
  """
  try:
    g.conn.close()
  except Exception as e:
    pass


#
# @app.route is a decorator around index() that means:
#   run index() whenever the user tries to access the "/" path using a GET request
#
# If you wanted the user to go to e.g., localhost:8111/foobar/ with POST or GET then you could use
#
#       @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: http://flask.pocoo.org/docs/0.10/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
#
@app.route('/')
def index():
  """
  request is a special object that Flask provides to access web request information:

  request.method:   "GET" or "POST"
  request.form:     if the browser submitted a form, this contains the data in the form
  request.args:     dictionary of URL arguments e.g., {a:1, b:2} for http://localhost?a=1&b=2

  See its API: http://flask.pocoo.org/docs/0.10/api/#incoming-request-data
  """

  # DEBUG: this is debugging code to see what request looks like
  print request.args


  #
  # example of a database query
  #
  cursor = g.conn.execute("SELECT name FROM test")
  names = []
  for result in cursor:
    names.append(result['name'])  # can also be accessed using result[0]
  cursor.close()

  #
  # Flask uses Jinja templates, which is an extension to HTML where you can
  # pass data to a template and dynamically generate HTML based on the data
  # (you can think of it as simple PHP)
  # documentation: https://realpython.com/blog/python/primer-on-jinja-templating/
  #
  # You can see an example template in templates/index.html
  #
  # context are the variables that are passed to the template.
  # for example, "data" key in the context variable defined below will be 
  # accessible as a variable in index.html:
  #
  #     # will print: [u'grace hopper', u'alan turing', u'ada lovelace']
  #     <div>{{data}}</div>
  #     
  #     # creates a <div> tag for each element in data
  #     # will print: 
  #     #
  #     #   <div>grace hopper</div>
  #     #   <div>alan turing</div>
  #     #   <div>ada lovelace</div>
  #     #
  #     {% for n in data %}
  #     <div>{{n}}</div>
  #     {% endfor %}
  #
  context = dict(data = names)


  #
  # render_template looks in the templates/ folder for files.
  # for example, the below file reads template/index.html
  #
  return render_template("index.html", **context)


@app.route('/restaurants')
def restaurants():
  print str(request.args)
  cursor = g.conn.execute("SELECT * FROM restaurants")
  names = []
  for result in cursor:
    names.append((result['restaurant_id'], result['restaurant_name']))  
  cursor.close()
  context = dict(data = names)
  return render_template("restaurants.html", **context)


@app.route('/menu')
def menu():
  if not 'rid' in request.args:
    return redirect('/restaurants')
  rid = request.args['rid']
  if not is_number(rid):
    return redirect('/restaurants')
  cursor = g.conn.execute("SELECT restaurant_name FROM restaurants as r where r.restaurant_id=%s", rid)
  if cursor.rowcount == 0:
    cursor.close()
    return redirect('/restaurants')
  rname = cursor.fetchone()['restaurant_name']
  cursor.close()
  cursor = g.conn.execute("SELECT m.menu_item_id, m.menu_name FROM menu_items as m, served_at as s where m.menu_item_id = s.menu_item_id and s.restaurant_id=%s", rid)
  names = []
  for result in cursor:
    names.append((result['menu_item_id'], result['menu_name']))  
  cursor.close()
  context = dict(data = names, rname = rname)
  return render_template("menu.html", **context)

@app.route('/reviews')
def reviews():
  if not 'mid' in request.args:
    return redirect('/restaurants')
  mid = request.args['mid']
  if not is_number(mid):
    return redirect('/restaurants')
  cursor = g.conn.execute("SELECT menu_name FROM menu_items as m where m.menu_item_id=%s", mid)
  if cursor.rowcount == 0:
    cursor.close()
    return redirect('/restaurants')
  mname = cursor.fetchone()['menu_name']
  cursor.close()
  cursor = g.conn.execute("SELECT u.email, u.first_name, s.review_time, s.rating, s.review_text from (select r.review_id, r.review_time, r.rating, r.review_text from reviews as r, (select review_id from rate where rate.menu_item_id=%s) as p where r.review_id = p.review_id) as s, users as u, create_review as c where c.email = u.email and c.review_id = s.review_id order by s.review_time DESC", mid)
  names = []
  for result in cursor:
    names.append((result[0], result[1], result[2], result[3], result[4]))
  cursor.close()
  cursor = g.conn.execute("SELECT avg(r.rating) from reviews as r, (select review_id from rate where rate.menu_item_id=%s) as p where r.review_id = p.review_id", mid)
  avg_rating = "{0:.2f}".format(cursor.fetchone()[0])
  cursor.close()
  context = dict(data = names, mname = mname, avg_rating = avg_rating)
  return render_template("reviews.html", **context)

@app.route('/user')
def user():
  if not 'uid' in request.args:
    return redirect('/restaurants')
  uid = request.args['uid']
  if not len(uid):
    return redirect('/restaurants')
  cursor = g.conn.execute("SELECT first_name, last_name FROM users as u where u.email=%s", uid)
  if cursor.rowcount == 0:
    cursor.close()
    return redirect('/restaurants')
  res = cursor.fetchone()
  uname = res['first_name'] + " " + res['last_name']
  cursor.close()
  cursor = g.conn.execute("SELECT rev.review_time, m.menu_item_id, m.menu_name, r.restaurant_id, r.restaurant_name, rev.rating, rev.review_text from reviews as rev, restaurants as r, menu_items as m, served_at as s, create_review as c, rate as q where c.email=%s and c.review_id=rev.review_id and rev.review_id=q.review_id and q.menu_item_id=m.menu_item_id and m.menu_item_id=s.menu_item_id and s.restaurant_id=r.restaurant_id order by rev.review_time DESC;", uid)
  names = []
  for result in cursor:
    names.append((result[0], result[1], result[2], result[3], result[4], result[5], result[6]))
  cursor.close()
  context = dict(data = names, uname = uname)
  return render_template("user.html", **context)

def is_number(s):
  try:
    int(s)
    return True
  except ValueError:
    return False

#
# This is an example of a different path.  You can see it at
# 
#     localhost:8111/another
#
# notice that the functio name is another() rather than index()
# the functions for each app.route needs to have different names
#
@app.route('/another')
def another():
  return render_template("anotherfile.html")


@app.route('/search')
def search():
  cuisines = []
  cursor = g.conn.execute("SELECT cuisine_name FROM cuisines")

  for result in cursor:
    cuisines.append(result['cuisine_name'])  

  cursor.close()

  context = dict(data = cuisines)
  return render_template("search.html", **context)


@app.route('/results')
def results():
  if not "inputZip" in request.args or not "inputCuisine" in request.args:
    return redirect("/restaurants")

  zipcode = request.args["inputZip"]
  cuisine = request.args["inputCuisine"]
  results = [cuisine, zipcode]

  cursor = g.conn.execute(
    """
    SELECT rests.menu_name, rests.restaurant_name, avg(r.rating) AS avg_rating, rests.restaurant_id, rests.menu_item_id
    FROM reviews AS r, rate AS t, (
      SELECT n.menu_item_id, n.menu_name, res.restaurant_name, res.restaurant_id
      FROM served_at AS s, restaurants AS res, located_at AS loc, address AS a, (
        SELECT m.menu_item_id, m.menu_name 
        FROM menu_items AS m, belongs_to AS b 
        WHERE b.cuisine_name = %s AND b.menu_item_id = m.menu_item_id
      ) AS n 
      WHERE s.restaurant_id = res.restaurant_id AND res.restaurant_id = loc.address_id AND loc.address_id = a.address_id AND
      a.zipcode = %s AND s.menu_item_id = n.menu_item_id
    ) AS rests 
    WHERE t.menu_item_id = rests.menu_item_id and t.review_id = r.review_id 
    GROUP BY rests.menu_name, rests.restaurant_name, rests.restaurant_id, rests.menu_item_id
    ORDER BY avg_rating DESC;
    """, cuisine, zipcode)

  if cursor.rowcount == 0:
    cursor.close()
    return redirect("/noresults")

  for result in cursor:
    temp = [result[0], result[1], result[2], result[3], result[4]]
    temp[2] = "{0:.2f}".format(temp[2]) + " / 10"
    results.append(temp)

  cursor.close()

  context = dict(data = results)
  return render_template("results.html", **context)



# Example of adding new data to the database
@app.route('/add', methods=['POST'])
def add():
  name = request.form['name']
  print name
  cmd = 'INSERT INTO test(name) VALUES (:name1), (:name2)';
  g.conn.execute(text(cmd), name1 = name, name2 = name);
  return redirect('/')


@app.route('/login')
def login():
    abort(401)
    this_is_never_executed()


if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=8111, type=int)
  def run(debug, threaded, host, port):
    """
    This function handles command line parameters.
    Run the server using

        python server.py

    Show the help text using

        python server.py --help

    """

    HOST, PORT = host, port
    print "running on %s:%d" % (HOST, PORT)
    app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)


  run()
