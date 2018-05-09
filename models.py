#! /usr/bin/env python3

from sqlalchemy import (create_engine, Column, Integer,
                        String, ForeignKey, DateTime, event)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from passlib.apps import custom_app_context as pwd_context
from datetime import datetime
import random
import string
from slugify import slugify
from itsdangerous import (TimedJSONWebSignatureSerializer as Serializer,
                          BadSignature, SignatureExpired)

Base = declarative_base()
secret_key = ''.join(random.choice(
    string.ascii_uppercase + string.digits) for x in range(32))


class User(Base):

    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    picture = Column(String)
    email = Column(String)
    password_hash = Column(String(64))

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def generate_auth_token(self, expiration=600):
        s = Serializer(secret_key, expires_in=expiration)
        return s.dumps({'id': self.id})

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(secret_key)
        try:
            data = s.loads(token)
        except SignatureExpired:
            # Valid Token, but expired
            return None
        except BadSignature:
            # Invalid Token
            return None
        user_id = data['id']
        return user_id

    @property
    def serialize(self):
        """Serialize object as JSON object"""
        return {
            "id": self.id,
            "name": self.name,
            "picture": self.picture
        }


class League(Base):

    __tablename__ = 'league'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    slug = Column(String, index=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'))
    user = relationship('User', backref=backref(
        'leagues', cascade="all,delete"))

    @property
    def serialize(self):
        teams = [t.serialize for t in self.teams]
        games = [g.serialize for g in self.games]
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "teams": teams,
            "games": games
        }

    @staticmethod
    def generate_slug(target, value, oldvalue, initiator):
        if value and (not target.slug or value != oldvalue):
            target.slug = slugify(value)
        return


class Team(Base):

    __tablename__ = 'team'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    slug = Column(String, index=True)
    league_id = Column(Integer, ForeignKey('league.id', ondelete='CASCADE'))
    league = relationship('League', backref=backref(
        'teams', cascade="all,delete"))

    @property
    def serialize(self):
        """Serialize object as JSON"""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug
        }

    @staticmethod
    def generate_slug(target, value, oldvalue, initiator):
        if value and (not target.slug or value != oldvalue):
            target.slug = slugify(value)
        return


class ScheduledGame(Base):

    __tablename__ = 'scheduled_game'
    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey('league.id', ondelete='CASCADE'))
    league = relationship('League', backref=backref(
        'games', cascade="all,delete"))
    home_team_id = Column(Integer, ForeignKey('team.id', ondelete='CASCADE'))
    home_team = relationship('Team', foreign_keys=[home_team_id],
                             backref=backref('home_game', cascade="all,delete"))  # noqa
    away_team_id = Column(Integer, ForeignKey('team.id', ondelete='CASCADE'))
    away_team = relationship('Team', foreign_keys=[away_team_id],
                             backref=backref('away_game', cascade="all,delete"))  # noqa
    date_time = Column(DateTime, default=datetime.now())

    @property
    def serialize(self):
        dict = {
            "id": self.id,
            "league": self.league.name,
            "home_team": self.home_team.name,
            "away_team": self.away_team.name,
            "date_time": self.date_time,
        }
        if self.result is not None:
            dict['result'] = self.result.serialize
        return dict


class GameResult(Base):

    __tablename__ = 'game_result'
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('scheduled_game.id'))
    game = relationship('ScheduledGame',
                        backref=backref("result", cascade="all,delete",
                                        uselist=False))
    away_score = Column(Integer)
    home_score = Column(Integer)

    @property
    def serialize(self):
        return {
            "id": self.id,
            "away_score": self.away_score,
            "home_score": self.home_score
        }


event.listen(League.name, 'set', League.generate_slug, retval=False)
event.listen(Team.name, 'set', Team.generate_slug, retval=False)

engine = create_engine('postgresql://catalog:catalog@localhost/catalog')


Base.metadata.create_all(engine)
