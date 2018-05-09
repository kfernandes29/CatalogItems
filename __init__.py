#! /usr/bin/env python3

import os
import requests
import random
import string
import json
from datetime import datetime
from slugify import slugify
from functools import wraps
from flask import (request, Flask, jsonify, render_template,
                   session as login_session, make_response,
                   flash, redirect, url_for)
from models import Base, User, League, ScheduledGame, GameResult, Team
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from oauth2client.client import flow_from_clientsecrets, FlowExchangeError

engine = create_engine('postgresql://catalog:catalog@localhost/catalog')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()
app = Flask(__name__)

base_dir = os.path.dirname(__file__)
google_clients_secrets = os.path.join(base_dir, 'google_clients_secrets.json')

GOOGLE_CLIENT_ID = json.loads(open(google_clients_secrets).read())[
    'web']['client_id']
# FB_APP_ID = json.loads(
# open('facebook_clients_secrets.json').read())['web']['app_id']
# FB_APP_SECRET = json.loads(
# open('facebook_clients_secrets.json').read())['web']['app_secret']


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in login_session:
            flash("Please login to gain authorization.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Authentication - Login


@app.route('/login')
def login():
    # Generate a random string for the state
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in range(32))
    login_session['state'] = state
    return render_template('login.html', state=state, facebook_app_id="",
                           google_client_id=GOOGLE_CLIENT_ID)


# Authentication - Logout


@app.route('/logout')
def logout():
    # Check for provider key in login_session
    if 'provider' in login_session:
        # If provider is 'google' then call google disconnect
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
        # If provider is 'facebook' then call facebook disconnect
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        # Remove login-session values
        del login_session['user_id']
        del login_session['name']
        del login_session['email']
        del login_session['picture']
        del login_session['provider']
        del login_session['access_token']
        flash("You have successfully logged out.")
    else:
        flash("Could not log you out.")
    return redirect(url_for("showLeagues"))

# Facebook OAuth


@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps("Invalid state parameter"), 400)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Exchange short-live token for long-live token
    access_token = request.data
    url = ("https://graph.facebook.com/oauth/access_token?"
           "grant_type=fb_exchange_token&client_id={}&client_secret={}"
           "&fb_exchange_token={}").format("", "", access_token.decode())
    result = requests.get(url)
    credentials = result.json()
    # Retrieve profile information from facebook
    user_url = ("https://graph.facebook.com/v2.12/me?access_token={}"
                "&fields=id,name,email").format(credentials['access_token'])
    user = requests.get(user_url)
    data = user.json()
    # Add user information to session
    login_session['provider'] = 'facebook'
    login_session['access_token'] = credentials['access_token']
    login_session['name'] = data['name']
    login_session['email'] = data['email']
    login_session['facebook_id'] = data['id']
    # Get picture url
    picture_url = ("https://graph.facebook.com/v2.12/me/picture?"
                   "access_token={}&redirect=0&height=200&width=200").format(
        credentials['access_token'])
    picture_result = requests.get(picture_url)
    picture = picture_result.json()
    login_session['picture'] = picture['data']['url']
    # Check if User exists with email address
    user_id = getUserId(login_session['email'])
    # If user does not exist, create one
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id
    output = ("</br></br><h1>Welcome, {}</h1>"
              "</br></br><p>Redirecting.......</p>")
    return output.format(login_session['name'])


def fbdisconnect():
    # Disconnect the connected user
    access_token = login_session['access_token']
    # Execute DELETE request to revoke token
    url = ("https://graph.facebook.com/v2.12/me/permissions?"
           "access_token={}").format(access_token)
    requests.delete(url)

# Google OAuth


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data
    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets(
            google_clients_secrets, scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ("https://www.googleapis.com/oauth2/v1/tokeninfo?"
           "access_token={}").format(access_token)
    result = requests.get(url).json()
    # If there was an error in the access token info, abort.
    if 'error' in result:
        response = make_response(json.dumps(result['error']), 500)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Verify that the access token is valid for this app.
    if result['issued_to'] != GOOGLE_CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print("Token's client ID does not match app's.")
        response.headers['Content-Type'] = 'application/json'
        return response
    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id
    login_session['provider'] = 'google'
    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)
    data = answer.json()
    login_session['name'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    user_id = getUserId(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id
    output = ("</br></br><h1>Welcome, {}</h1>"
              "</br></br><p>Redirecting.......</p>")
    return output.format(login_session['name'])


def gdisconnect():

    # Disconnect the connected user
    access_token = login_session['access_token']
    # Execute GET request to revoke token
    url = ("https://accounts.google.com/o/oauth2/revoke?"
           "token={}").format(access_token)
    requests.get(url)

# Helpers


def getUserInfo(user_id):
    """Return user by user_id"""
    return session.query(User).filter_by(id=user_id).one()


def getUserId(email):
    """Return user by email address"""
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except Exception:
        return None


def createUser(login_session):
    """Create a user using login_session values"""
    # Create a new User
    newUser = User(name=login_session['name'], email=login_session['email'],
                   picture=login_session['picture'])
    # Add new user to session
    session.add(newUser)
    # Commit the session
    session.commit()
    # Return created User from database
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id

# JSON API


# Routes

# CRUD Leagues


@app.route('/')
@app.route('/leagues')
def showLeagues():
    """Endpoint to display leagues"""
    # Return all leagues
    leagues = session.query(League).all()
    # Return the last 10 scheduled games without results
    upcoming = session.query(ScheduledGame).filter(
        ScheduledGame.result == None).order_by(
        ScheduledGame.date_time.asc()).limit(10).all()  # noqa
    # Return the last 10 games with results
    completed = session.query(ScheduledGame).filter(
        ScheduledGame.result != None).limit(10).all()  # noqa
    # Render template
    return render_template('index.html', leagues=leagues, upcoming=upcoming,
                           completed=completed)


@app.route('/leagues/json')
def leaguesJSON():
    """Return /leagues as JSON object"""
    try:
        leagues = session.query(League).all()
    except Exception:
        leagues = []
    return jsonify(leagues=[l.serialize for l in leagues])


@app.route('/leagues/<league_id>')
def showLeague(league_id):
    """Show a specific league either by slug or id"""
    # Return a League by id
    league = session.query(League).filter_by(slug=league_id).first()
    # If could not get League by ID, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Get Last 10 upcoming games for league
    try:
        upcoming = session.query(ScheduledGame).filter(
            ScheduledGame.result == None).filter_by(
            league=league).order_by(
            ScheduledGame.date_time.asc()).limit(10).all()  # noqa
    except Exception:
        upcoming = []
    # Get last 10 completed games for league
    try:
        completed = session.query(ScheduledGame).filter_by(
            league=league).filter(
            ScheduledGame.result != None).limit(10).all()   # noqa
    except Exception:
        completed = []
    return render_template('league.html', league=league, teams=league.teams,
                           upcoming=upcoming, completed=completed)


@app.route('/leagues/<league_id>/json')
def leagueJSON(league_id):
    """Return league as JSON object"""
    league = session.query(League).filter_by(slug=league_id).first()
    # If League is None, then a slug was provided
    if league is None:
        # Return League by slug
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return jsonify(league=[])
    return jsonify(league.serialize)


@app.route('/leagues/new', methods=['GET', 'POST'])
@login_required
def createLeague():
    """Create a new League"""
    # If method is POST
    if request.method == 'POST':
        # Create an SEO friendly slug for the new league
        slug = slugify(request.form['name'])
        # Check if a league exists with this slug
        league = session.query(League).filter_by(slug=slug).first()
        if league is not None:
            flash("A league with this name already exists.")
            return redirect(url_for('createLeague'))
        # Create a new League
        league = League(name=request.form['name'],
                        user_id=login_session['user_id'])
        session.add(league)
        session.commit()
        flash("Successfully created new league: {}".format(league.name))
        return redirect(url_for('showLeague', league_id=league.slug))
    # Show create league template
    return render_template('create_league.html')


@app.route('/leagues/<league_id>/edit', methods=['GET', 'POST'])
@login_required
def editLeague(league_id):
    """Edit a league"""
    league = session.query(League).filter_by(slug=league_id).first()
    # If no league was found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Check if logged in user has authorization to edit league
    if league.user_id != login_session['user_id']:
        flash("You do not have authorization to perform this action.")
        return render_template('denied.html')
    # If method is POST
    if request.method == 'POST':
        # Check if league exists with new slug
        slug = slugify(request.form['name'])
        try:
            exists = session.query(League).filter_by(slug=slug).first()
        except Exception:
            exists = None
        if exists is not None:
            flash("A league with this name already exists.")
            return redirect(url_for('editLeague', league_id=league.slug))
        # Edit the league and save to database
        if request.form['name']:
            league.name = request.form['name']
        session.add(league)
        session.commit()
        flash("Successfully edited league {}".format(league.name))
        return redirect(url_for('showLeague', league_id=league.slug))
    # Show the edit League template
    return render_template('edit_league.html', league=league)


@app.route('/leagues/<league_id>/delete', methods=['GET', 'POST'])
@login_required
def deleteLeague(league_id):
    """Delete a League"""
    league = session.query(League).filter_by(slug=league_id).first()
    # If no League was found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Check if user has authorization to delete this league
    if league.user_id != login_session['user_id']:
        flash("You do not have authorization to perform this action.")
        return render_template('denied.html')
    # If method is POST
    if request.method == 'POST':
        # Delete the league from the database
        session.delete(league)
        session.commit()
        flash("Successfully deleted {}".format(league.name))
        return redirect(url_for('showLeagues'))
    # Show delete league template
    return render_template('delete_league.html', league=league)

# CRUD Team


@app.route('/leagues/<league_id>/<team_id>')
def showTeam(league_id, team_id):
    """Show a Team"""
    league = session.query(League).filter_by(slug=league_id).first()
    # If not league was found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    team = session.query(Team).filter_by(
        slug=team_id, league=league).first()
    # If no team was found, try by slug
    if team is None:
        try:
            team = session.query(Team).get(team_id)
        except Exception:
            return render_template('404.html')
    # Return Team template
    return render_template('team.html', league=league, team=team)


@app.route('/leagues/<league_id>/<team_id>/json')
def teamsJSON(league_id, team_id):
    """Return Team as JSON object"""
    league = session.query(League).filter_by(slug=league_id).first()
    # If not league was found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    team = session.query(Team).filter_by(
        slug=team_id, league=league).first()
    # If no team was found, then try by slug
    if team is None:
        try:
            team = session.query(Team).get(team_id)
        except Exception:
            return render_template('404.html')
    # Get games belonging to team
    try:
        games = session.query(ScheduledGame).filter_by(
            league_id=team.league.id).all()
    except Exception:
        games = []
    return jsonify(team=team.serialize, games=[g.serialize for g in games])


@app.route('/leagues/<league_id>/teams/new', methods=['GET', 'POST'])
@login_required
def createTeam(league_id):
    """Create a Team"""
    league = session.query(League).filter_by(slug=league_id).first()
    # If league is not found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Authorization to check if league owner
    if league.user_id != login_session['user_id']:
        flash("You do not have authorization to perform this action.")
        return render_template('denied.html')
    # If method is POST
    if request.method == 'POST':
        # Check if a team exists with this slug
        slug = slugify(request.form['name'])
        try:
            team = session.query(Team).filter_by(
                slug=slug, league=league).first()
        except Exception:
            pass
        if team is not None:
            flash("A team with this name already exists.")
            return redirect(url_for('createTeam', league_id=league.id))
        # Create a new team
        team = Team(name=request.form['name'], league_id=league.id)
        session.add(team)
        session.commit()
        flash("Successfully added the {} to {}".format(
            team.name, team.league.name))
        return redirect(url_for('showLeague', league_id=team.league.slug))
    return render_template('create_team.html', league=league)


@app.route('/leagues/<league_id>/<team_id>/edit', methods=['GET', 'POST'])
@login_required
def editTeam(league_id, team_id):
    """Edit a Team"""
    league = session.query(League).filter_by(slug=league_id).first()
    # If no league found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Get team
    team = session.query(Team).filter_by(
        slug=team_id, league=league).first()
    # If team not found, try by slug
    if team is None:
        try:
            team = session.query(Team).get(team_id)
        except Exception:
            return render_template('404.html')
    # Authorization if current user owns league object
    if team.league.user_id != login_session['user_id']:
        flash("You do not have authorization to perform this action.")
        return render_template('denied.html')
    # If method is POST
    if request.method == 'POST':
        # Check if team exists with this slug
        slug = slugify(request.form['name'])
        exists = session.query(Team).filter_by(
            slug=slug, league=league).first()
        if exists is not None:
            flash("A team with this name exists.")
            return redirect(url_for('editTeam', league_id=league.slug,
                                    team_id=team.slug))
        if request.form['name']:
            team.name = request.form['name']
        # Save changes
        session.add(team)
        session.commit()
        flash("Successfully edited {}".format(team.name))
        return redirect(url_for('showLeague', league_id=league.slug))
    # Render edit team template
    return render_template('edit_team.html', league=league, team=team)


@app.route('/leagues/<league_id>/<team_id>/delete', methods=['GET', 'POST'])
@login_required
def deleteTeam(league_id, team_id):
    """Delete a team"""
    # Get league by ID
    league = session.query(League).filter_by(slug=league_id).first()
    # If league not found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Get team by ID
    team = session.query(Team).filter_by(
        slug=team_id, league=league).first()
    # If team not found, try by slug
    if team is None:
        try:
            team = session.query(Team).get(team_id)
        except Exception:
            return render_template('404.html')
    # Check authorization to delete team
    if team.league.user_id != login_session['user_id']:
        flash("You do not have authorization to perform this action.")
        return render_template('denied.html')
    # Delete the team
    if request.method == 'POST':
        session.delete(team)
        session.commit()
        flash("Successfully deleted the {} from {}".format(team.name,
                                                           league.name))
        return redirect(url_for('showLeague', league_id=league.slug))
    # Render delete team template
    return render_template('delete_team.html', league=league, team=team)

# CRUD Games


@app.route('/leagues/<league_id>/games/new', methods=['GET', 'POST'])
@login_required
def createGame(league_id):
    """Create a Game"""
    league = session.query(League).filter_by(slug=league_id).first()
    # If league not found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Authorization for league owner
    if league.user_id != login_session['user_id']:
        flash("You do not have authorization to perform this action.")
        return render_template('denied.html')
    # If method is POST
    if request.method == 'POST':
        # Make sure home and away teams arent the same
        if request.form['home_team'] == request.form['away_team']:
            flash("The home team and away team can not be the same.")
            return redirect(url_for('createGame', league_id=league.id))
        # Create Game
        dt = datetime.strptime(request.form['date_time'], '%m-%d-%Y %I:%M%p')
        game = ScheduledGame()
        game.home_team_id = request.form['home_team']
        game.away_team_id = request.form['away_team']
        game.date_time = dt
        game.league = league
        session.add(game)
        session.commit()
        flash("Successfully add a game to {}".format(league.name))
        return redirect(url_for('showLeague', league_id=league.slug))
        # Render create game template
    teams = session.query(Team).filter_by(league_id=league.id).all()
    return render_template('create_game.html', league=league, teams=teams)


@app.route('/leagues/<league_id>/games/<game_id>/edit', methods=['GET', 'POST'])  # noqa
@login_required
def editGame(league_id, game_id):
    """Edit a Game"""
    league = session.query(League).filter_by(slug=league_id).first()
    # If league not found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Authorization for league owner
    if league.user_id != login_session['user_id']:
        flash("You do not have authorization to perform this action.")
        return render_template('denied.html')
    # Get game by ID
    try:
        game = session.query(ScheduledGame).get(game_id)
    except Exception:
        return render_template('404.html')
    # Save game using form data
    if request.method == 'POST':
        dt = datetime.strptime(request.form['date_time'], '%m-%d-%Y %I:%M%p')
        if request.form['date_time']:
            game.date_time = dt
        session.add(game)
        session.commit()
        flash("Successfully edited game.")
        return redirect(url_for('showLeague', league_id=league.slug))
    # Render edit game
    return render_template('edit_game.html', league=league, game=game)


@app.route('/leagues/<league_id>/games/<game_id>/delete', methods=['GET', 'POST'])  # noqa
@login_required
def deleteGame(league_id, game_id):
    """Delete a Game"""
    league = session.query(League).filter_by(slug=league_id).first()
    # If league not found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Authorization for league owner
    if league.user_id != login_session['user_id']:
        flash("You do not have authorization to perform this action.")
        return render_template('denied.html')
    # Get game by ID
    try:
        game = session.query(ScheduledGame).get(game_id)
    except Exception:
        return render_template('404.html')
    # Save game using form data
    if request.method == 'POST':
        session.delete(game)
        session.commit()
        flash("Successfully deleted game.")
        return redirect(url_for('showLeague', league_id=league.slug))
    # Render edit game
    return render_template('delete_game.html', league=league, game=game)

# CRUD Results


@app.route('/leagues/<league_id>/games/<game_id>/results/new', methods=['GET', 'POST'])  # noqa
@login_required
def createResult(league_id, game_id):
    """Create a Result"""
    # Find league by ID
    league = session.query(League).filter_by(slug=league_id).first()
    # If league not found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Find game by ID
    try:
        game = session.query(ScheduledGame).get(game_id)
    except Exception:
        return render_template('404.html')
    # Authorization for league owner
    if league.user_id != login_session['user_id']:
        flash("You do not have authorization to perform this action.")
        return render_template('denied.html')
    # If method is POST
    if request.method == 'POST':
        # Create a new game result
        result = GameResult(game_id=game.id,
                            away_score=request.form['away_score'],
                            home_score=request.form['home_score'])
        session.add(result)
        session.commit()
        flash("Successfully added result")
        return redirect(url_for('showLeague', league_id=league.slug))
    # Render create result template
    return render_template('create_result.html', league=league, game=game)


@app.route('/leagues/<league_id>/games/<game_id>/results/edit', methods=['GET', 'POST'])  # noqa
@login_required
def editResult(league_id, game_id):
    """Edit a game result"""
    # Find league by ID
    league = session.query(League).filter_by(slug=league_id).first()
    # If no league found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Find a game by ID
    try:
        game = session.query(ScheduledGame).get(game_id)
    except Exception:
        return render_template('404.html')
    # Authorization for league owner
    if league.user_id != login_session['user_id']:
        flash("You do not have authorization to perform this action.")
        return render_template('denied.html')
    # If method is POST
    if request.method == 'POST':
        # Edit the game result
        if request.form['home_score']:
            game.result.home_score = request.form['home_score']
        if request.form['away_score']:
            game.result.away_score = request.form['away_score']
        session.add(game.result)
        session.commit()
        flash("Successfully edited result")
        return redirect(url_for('showLeague', league_id=league.slug))
    # Render edit result template
    return render_template('edit_result.html', league=league, game=game)


@app.route('/leagues/<league_id>/games/<game_id>/results/delete', methods=['GET', 'POST'])  # noqa
@login_required
def deleteResult(league_id, game_id):
    """Delete a game result"""
    # Find league by ID
    league = session.query(League).filter_by(slug=league_id).first()
    # If no league found, try by slug
    if league is None:
        try:
            league = session.query(League).get(league_id)
        except Exception:
            return render_template('404.html')
    # Get game by ID
    try:
        game = session.query(ScheduledGame).get(game_id)
    except Exception:
        return render_template('404.html')
    # Authorization for league owner
    if league.user_id != login_session['user_id']:
        flash("You do not have authorization to perform this action.")
        return render_template('denied.html')
    # If method is POST
    if request.method == 'POST':
        # Delete game result
        session.delete(game.result)
        session.commit()
        flash("Successfully deleted result")
        return redirect(url_for('showLeague', league_id=league.slug))
    # Render delete result template
    return render_template('delete_result.html', league=league, game=game)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0')
