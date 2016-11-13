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
from functools import wraps
from flask import Flask, session, request, render_template, g, redirect, Response

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

with open('password.txt', 'r') as f:
  passwd = f.readline()

DATABASEURI = 'postgresql://ss4924:' + passwd.strip() + '@104.196.175.120/postgres'
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

def login_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if 'user' not in session:
      return redirect('/login')
    return f(*args, **kwargs)
  return decorated_function

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
@login_required
def index():
  return render_template('index.html')


@app.route('/restaurants')
@login_required
def restaurants():
  cursor = g.conn.execute("SELECT r.restaurant_id, r.restaurant_name, a.zipcode from restaurants as r, located_at as l, address as a where l.restaurant_id=r.restaurant_id and a.address_id=l.address_id")
  names = []
  for result in cursor:
    names.append((result['restaurant_id'], result['restaurant_name'], result['zipcode']))
  cursor.close()
  context = dict(data = names)
  return render_template('restaurants.html', **context)


@app.route('/menu')
@login_required
def menu():
  if not 'rid' in request.args:
    return redirect('/')
  rid = request.args['rid']
  if not is_number(rid):
    return redirect('/')
  cursor = g.conn.execute("SELECT restaurant_name FROM restaurants as r where r.restaurant_id=%s", rid)
  if cursor.rowcount == 0:
    cursor.close()
    return redirect('/')
  rname = cursor.fetchone()['restaurant_name']
  cursor.close()
  cursor = g.conn.execute("SELECT m.menu_item_id, m.menu_name, c.cuisine_name, avg(r.rating) as avg, count(r.rating) as cnt FROM menu_items as m, served_at as s, reviews as r, rate as q, cuisines as c, belongs_to as b where b.menu_item_id=m.menu_item_id and c.cuisine_name=b.cuisine_name and m.menu_item_id = s.menu_item_id and s.restaurant_id=%s and q.menu_item_id=m.menu_item_id and q.review_id=r.review_id group by m.menu_name, m.menu_item_id, c.cuisine_name order by avg DESC", rid)
  names = []
  for result in cursor:
    avg = '{0:.2f}'.format(result['avg']) + ' / 10'
    names.append((result['menu_item_id'], result['menu_name'], result['cuisine_name'], avg, result['cnt']))
  cursor.close()
  cursor = g.conn.execute("SELECT m.menu_item_id, m.menu_name, c.cuisine_name FROM menu_items as m, served_at as s, rate as q, cuisines as c, belongs_to as b where b.menu_item_id=m.menu_item_id and c.cuisine_name=b.cuisine_name and m.menu_item_id=s.menu_item_id and s.restaurant_id=%s and not exists (select * from rate where rate.menu_item_id=m.menu_item_id) group by m.menu_item_id, m.menu_name, c.cuisine_name order by c.cuisine_name", rid)
  for result in cursor:
    names.append((result['menu_item_id'], result['menu_name'], result['cuisine_name'], 'n/a', 0))
  cursor.close()
  if not len(names):
    return redirect('/noresults')
  context = dict(data = names, rname = rname)
  return render_template('menu.html', **context)

@app.route('/reviews')
@login_required
def reviews():
  if not 'mid' in request.args:
    return redirect('/')
  mid = request.args['mid']
  if not is_number(mid):
    return redirect('/')
  cursor = g.conn.execute("SELECT menu_name FROM menu_items as m where m.menu_item_id=%s", mid)
  if cursor.rowcount == 0:
    cursor.close()
    return redirect('/')
  mname = cursor.fetchone()['menu_name']
  cursor.close()
  cursor = g.conn.execute("SELECT u.email, u.first_name, s.review_time, s.rating, s.review_text from (select r.review_id, r.review_time, r.rating, r.review_text from reviews as r, (select review_id from rate where rate.menu_item_id=%s) as p where r.review_id = p.review_id) as s, users as u, create_review as c where c.email = u.email and c.review_id = s.review_id order by s.review_time DESC", mid)
  if cursor.rowcount == 0:
    cursor.close()
    return redirect('/noresults')
  names = []
  for result in cursor:
    names.append((result[0], result[1], result[2], result[3], result[4]))
  cursor.close()
  cursor = g.conn.execute("SELECT avg(r.rating) from reviews as r, (select review_id from rate where rate.menu_item_id=%s) as p where r.review_id = p.review_id", mid)
  avg_rating = '{0:.2f}'.format(cursor.fetchone()[0]) + ' / 10'
  cursor.close()
  context = dict(data = names, mname = mname, avg_rating = avg_rating)
  return render_template('reviews.html', **context)

@app.route('/user')
@login_required
def user():
  if not 'uid' in request.args:
    return redirect('/')
  uid = request.args['uid']
  if not len(uid):
    return redirect('/')
  cursor = g.conn.execute("SELECT first_name, last_name FROM users as u where u.email=%s", uid)
  if cursor.rowcount == 0:
    cursor.close()
    return redirect('/')
  res = cursor.fetchone()
  uname = res['first_name'] + " " + res['last_name']
  cursor.close()
  cursor = g.conn.execute("SELECT rev.review_time, m.menu_item_id, m.menu_name, r.restaurant_id, r.restaurant_name, rev.rating, rev.review_text from reviews as rev, restaurants as r, menu_items as m, served_at as s, create_review as c, rate as q where c.email=%s and c.review_id=rev.review_id and rev.review_id=q.review_id and q.menu_item_id=m.menu_item_id and m.menu_item_id=s.menu_item_id and s.restaurant_id=r.restaurant_id order by rev.review_time DESC;", uid)
  if cursor.rowcount == 0:
    cursor.close()
    return redirect('/noresults')
  names = []
  for result in cursor:
    names.append((result[0], result[1], result[2], result[3], result[4], result[5], result[6]))
  cursor.close()
  context = dict(data = names, uname = uname)
  return render_template('user.html', **context)

@app.route('/add_review', methods=['POST'])
def add_review():
  comment = request.form['comment']
  rating = request.form['rating']
  print comment
  print rating
  # first_name = request.form['first_name']
  # last_name = request.form['last_name']
  # dob = request.form['dob']
  # cursor = g.conn.execute("SELECT * FROM users WHERE users.email=%s", email)
  # if cursor.rowcount:
  #   return redirect('/login?m=2')
  # g.conn.execute('INSERT INTO users VALUES (%s, %s, %s, %s, DATE%s)', email, first_name, last_name, password, dob);
  # session['user'] = email
  return redirect('/')

@app.route('/noresults')
@login_required
def noresults():
  return render_template('noresults.html')

def is_number(s):
  try:
    int(s)
    return True
  except ValueError:
    return False

@app.route('/search')
@login_required
def search():
  cuisines = []
  cursor = g.conn.execute("SELECT cuisine_name FROM cuisines")

  for result in cursor:
    cuisines.append(result['cuisine_name'])  

  cursor.close()

  context = dict(data = sorted(cuisines))
  return render_template('search.html', **context)


@app.route('/results')
@login_required
def results():
  if not 'inputZip' in request.args or not 'inputCuisine' in request.args:
    return redirect('/')

  results = []
  zipcode = request.args['inputZip']
  cuisine = request.args['inputCuisine']

  cursor = g.conn.execute(
    """
    SELECT rests.menu_item_id, rests.menu_name, rests.restaurant_id, rests.restaurant_name, avg(r.rating) AS avg_rating
    FROM (reviews INNER JOIN rate ON reviews.review_id = rate.review_id) AS r RIGHT JOIN (
      SELECT n.menu_item_id, n.menu_name, res.restaurant_name, res.restaurant_id
      FROM served_at AS s, restaurants AS res, located_at AS loc, address AS a, (
        SELECT m.menu_item_id, m.menu_name 
        FROM menu_items AS m, belongs_to AS b 
        WHERE b.cuisine_name = %s AND b.menu_item_id = m.menu_item_id
      ) AS n 
      WHERE s.restaurant_id = res.restaurant_id AND res.restaurant_id = loc.address_id AND 
      loc.address_id = a.address_id AND a.zipcode = %s AND s.menu_item_id = n.menu_item_id
    ) AS rests
    ON r.menu_item_id = rests.menu_item_id 
    GROUP BY rests.menu_name, rests.restaurant_name, rests.restaurant_id, rests.menu_item_id
    ORDER BY avg_rating DESC;
    """, cuisine, zipcode)

  if cursor.rowcount == 0:
    cursor.close()
    return redirect('/noresults')

  for result in cursor:
    temp = [result[0], result[1], result[2], result[3], result[4]]

    if temp[4] == "":
      temp[4] = "n/a"
      
    temp[4] = '{0:.2f}'.format(temp[2]) + " / 10"
    results.append(temp)

  cursor.close()

  context = dict(data = results, cuisine = cuisine, zipcode = zipcode)
  return render_template('results.html', **context)

@app.route('/login_user', methods=['POST'])
def login_user():
  email = request.form['email']
  password = request.form['password']
  cursor = g.conn.execute("SELECT password FROM users WHERE users.email=%s", email)
  if not cursor.rowcount:
    return redirect('/login?m=1')
  pw = cursor.fetchone()[0]
  if password != pw:
    return redirect('/login?m=0')
  session['user'] = email
  return redirect('/')

@app.route('/add_user', methods=['POST'])
def add_user():
  email = request.form['email']
  password = request.form['password']
  first_name = request.form['first_name']
  last_name = request.form['last_name']
  dob = request.form['dob']
  cursor = g.conn.execute("SELECT * FROM users WHERE users.email=%s", email)
  if cursor.rowcount:
    return redirect('/login?m=2')
  g.conn.execute('INSERT INTO users VALUES (%s, %s, %s, %s, DATE%s)', email, first_name, last_name, password, dob);
  session['user'] = email
  return redirect('/')


@app.route('/login')
def login():
  message1 = ''
  message2 = ''
  if 'm' in request.args:
    code = request.args['m']
    if code == '0':
      message1 = 'Incorrect password. Try again.'
    elif code == '1':
      message1 = 'Email not found. Please create account first.'  
    elif code == '2':
      message2 = 'Email already in use. Please log in.'
  context = dict(em1 = message1, em2 = message2)
  return render_template('login.html', **context)

@app.route('/logout')
def logout():
  session.pop('user', None)
  return redirect('/')

app.secret_key = 'secret_key'

if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=80, type=int)
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
