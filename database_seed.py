#! /usr/bin/env python3

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, League, Team, GameResult, ScheduledGame, User

engine = create_engine('postgresql://catalog:catalog@localhost/catalog')

Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

newUser1 = User(
    name="Gary Bettman", email="theboss@nhl.com", picture="")
session.add(newUser1)
session.commit()

newUser2 = User(
    name="Adam Silver", email="silverfox@nba.com", picture="")
session.add(newUser1)
session.commit()

# NHL

nhl = League(name="NHL", user=newUser1)
session.add(nhl)
session.commit()

leafs = Team(name="Toronto Maple Leafs", league=nhl)
session.add(leafs)
session.commit()

habs = Team(name="Montreal Canadiens", league=nhl)
session.add(habs)
session.commit()

pens = Team(name="Pittsburgh Penguins", league=nhl)
session.add(pens)
session.commit()

nhl_game1 = ScheduledGame(league_id=nhl.id, away_team_id=leafs.id,
                          home_team_id=habs.id)
session.add(nhl_game1)
session.commit()

nhl_game_result1 = GameResult(game_id=nhl_game1.id, home_score=5, away_score=3)
session.add(nhl_game_result1)
session.commit()

nhl_game2 = ScheduledGame(league_id=nhl.id, away_team_id=habs.id,
                          home_team_id=pens.id)
session.add(nhl_game2)
session.commit()

nhl_game_result2 = GameResult(game_id=nhl_game2.id, home_score=2, away_score=4)
session.add(nhl_game_result2)
session.commit()

nhl_game3 = ScheduledGame(league_id=nhl.id, away_team_id=pens.id,
                          home_team_id=leafs.id)
session.add(nhl_game3)
session.commit()

nhl_game_result3 = GameResult(game_id=nhl_game3.id, home_score=3, away_score=1)
session.add(nhl_game_result3)
session.commit()

# NBA

nba = League(name="NBA", user=newUser2)
session.add(nba)
session.commit()

raps = Team(name="Toronto Raptors", league=nba)
session.add(raps)
session.commit()

cavs = Team(name="Cleveland Cavaliers", league=nba)
session.add(cavs)
session.commit()

warriors = Team(name="Golden State Warriors", league=nba)
session.add(warriors)
session.commit()

print("Successfully seeded the database!!")
