from app import db
from datetime import datetime
from geoalchemy2 import Geometry
from datetime import date

class Country(db.Model):
    __tablename__ = 'countries'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    # Отношения
    commanders = db.relationship('Commander', back_populates='country')
    military_units = db.relationship('MilitaryUnit', back_populates='country')
    military_ranks = db.relationship('MilitaryRank', back_populates='country')

class MilitaryRank(db.Model):
    __tablename__ = 'military_ranks'
    
    id = db.Column(db.Integer, primary_key=True)
    rank_name = db.Column(db.String(100), nullable=False)
    rank_level = db.Column(db.Integer)
    
    # Внешние ключи
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'), nullable=False)
    
    # Отношения
    country = db.relationship('Country', back_populates='military_ranks')
    assignments = db.relationship(
        'CommanderRank', 
        back_populates='rank',
        foreign_keys='CommanderRank.rank_id'  # Явное указание
    )

class Commander(db.Model):
    __tablename__ = 'commanders'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    birth_date = db.Column(db.Date)
    death_date = db.Column(db.Date)
    biography = db.Column(db.Text)
    
    # Внешние ключи (исправленные имена таблиц)
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'), nullable=False)
    rank_id = db.Column(db.Integer, db.ForeignKey('commander_ranks.id'))
    
    # Отношения
    country = db.relationship('Country', back_populates='commanders')
    rank_assignments = db.relationship('CommanderRank', back_populates='commander', foreign_keys='CommanderRank.commander_id',  # Явное указание
        order_by='desc(CommanderRank.date_promoted)',
        cascade='all, delete-orphan')
    @property
    def current_rank(self):
        """Возвращает текущее звание командира"""
        return self.rank_assignments[0].rank if self.rank_assignments else None

    military_units = db.relationship('MilitaryUnit', back_populates='commander')
    #battle_participations = db.relationship('Battleparticipations', back_populates='commander')

class MilitaryUnit(db.Model):
    __tablename__ = 'military_units'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    formation_date = db.Column(db.Date)
    dissolution_date = db.Column(db.Date)
    
    # Внешние ключи (исправленные имена таблиц)
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'), nullable=False)
    parent_unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'))
    commander_id = db.Column(db.Integer, db.ForeignKey('commanders.id'))
    

    # Отношения
    country = db.relationship('Country', back_populates='military_units')
    commander = db.relationship('Commander', back_populates='military_units')
    parent = db.relationship('MilitaryUnit', remote_side=[id], backref='subunits')
    battle_participations = db.relationship('Battleparticipations', back_populates='unit',lazy=True, foreign_keys='[Battleparticipations.unit_id]')
    movements = db.relationship('UnitMovement', back_populates='unit')
    subordination_history = db.relationship(
        'UnitHierarchy',
        foreign_keys='UnitHierarchy.unit_id',
        back_populates='unit'
    )
    children = db.relationship('UnitHierarchy', foreign_keys='UnitHierarchy.parent_unit_id', back_populates='parent_unit')
    parent_relations = db.relationship('UnitHierarchy',foreign_keys='UnitHierarchy.parent_unit_id',back_populates='parent_unit')

    # Методы
    def get_current_parent(self):
        today = date.today()
        for record in self.subordination_history:
            if record.start_date <= today and (record.end_date is None or record.end_date >= today):
                return record.parent_unit
        return None

    def get_current_children(self):
        today = date.today()
        children = []
        for relation in self.parent_relations:
            if relation.start_date <= today and (relation.end_date is None or relation.end_date >= today):
                children.append(relation.unit)
        return children

class UnitHierarchy(db.Model):
    __tablename__ = 'unit_hierarchy'

    id_history = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'))
    parent_unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)

    # Отношения
    unit = db.relationship('MilitaryUnit', foreign_keys=[unit_id], back_populates='subordination_history')
    parent_unit = db.relationship('MilitaryUnit', foreign_keys=[parent_unit_id])

class Battle(db.Model):
    __tablename__ = 'battles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date_begin = db.Column(db.Date, nullable=False)
    date_end = db.Column(db.Date)
    description = db.Column(db.Text)
    victory = db.Column(db.String(40))

    # Внешние ключи
    place_id = db.Column(db.Integer, db.ForeignKey('places.id'))
    
    # Отношения
    place = db.relationship('Place', back_populates='battles')
    participations = db.relationship('Battleparticipations', back_populates='battle',foreign_keys='Battleparticipations.battle_id')
    trophies = db.relationship('Trophy', back_populates='battle')

class Battleparticipations(db.Model):
    __tablename__ = 'battle_participations'
    
    id = db.Column(db.Integer, primary_key=True)
    side = db.Column(db.String(20), nullable=False)
    #is_victor = db.Column(db.Boolean, default=False)
    
    # Внешние ключи (исправленные имена таблиц)
    battle_id = db.Column(db.Integer, db.ForeignKey('battles.id'), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'), nullable=False)
   # military_unit = db.relationship('MilitaryUnit', back_populates='battle_participations')
   # commander_id = db.Column(db.Integer, db.ForeignKey('commanders.id'))
    
    # Отношения
    battle = db.relationship('Battle', back_populates='participations', foreign_keys=[battle_id])
    unit = db.relationship('MilitaryUnit', back_populates='battle_participations', foreign_keys=[unit_id])
    #commander_id = db.relationship('Commander', back_populates='battle_participations')
    #losses = db.relationship('BattleLoss', back_populates='participations')

class BattleLoss(db.Model):
    __tablename__ = 'battle_losses'
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    count = db.Column(db.Integer, nullable=False)
    
    # Внешние ключи
    #participations_id = db.Column(db.Integer, db.ForeignKey('battle_participation.id'), nullable=False)
    
    # Отношения
    #participations = db.relationship('Battleparticipations', back_populates='losses')

class Trophy(db.Model):
    __tablename__ = 'trophies'
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    quantity = db.Column(db.Integer, default=1)
    
    # Внешние ключи
    battle_id = db.Column(db.Integer, db.ForeignKey('battles.id'), nullable=False)
    captor_id = db.Column(db.Integer, db.ForeignKey('military_units.id'))
    
    # Отношения
    battle = db.relationship('Battle', back_populates='trophies')
    captor = db.relationship('MilitaryUnit', backref='captured_trophies')

class Place(db.Model):
    __tablename__ = 'places'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    geom = db.Column(Geometry(geometry_type='POINT', srid=4326))
    
    # Отношения
    battles = db.relationship('Battle', back_populates='place')
    events = db.relationship('Event', back_populates='place')
    movements_from = db.relationship('UnitMovement', foreign_keys='UnitMovement.start_place_id', back_populates='start_place')
    movements_to = db.relationship('UnitMovement', foreign_keys='UnitMovement.end_place_id', back_populates='end_place')
    @property
    def latitude(self):
        """Получить широту из геометрии"""
        if self.geom is not None:
            return db.session.scalar(db.func.ST_Y(self.geom))
        return None

    @property
    def longitude(self):
        """Получить долготу из геометрии"""
        if self.geom is not None:
            return db.session.scalar(db.func.ST_X(self.geom))
        return None
    

class UnitMovement(db.Model):
    __tablename__ = 'unit_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    distance_km = db.Column(db.Float)
    route_description = db.Column(db.Text)
    
    # Внешние ключи
    unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'), nullable=False)
    start_place_id = db.Column(db.Integer, db.ForeignKey('places.id'), nullable=False)
    end_place_id = db.Column(db.Integer, db.ForeignKey('places.id'), nullable=False)
    
    # Отношения
    unit = db.relationship('MilitaryUnit', back_populates='movements')
    start_place = db.relationship('Place', foreign_keys=[start_place_id], back_populates='movements_from')
    end_place = db.relationship('Place', foreign_keys=[end_place_id], back_populates='movements_to')

class CommanderRank(db.Model):
    __tablename__ = 'commander_ranks'
    
    id = db.Column(db.Integer, primary_key=True)  # Добавляем автоинкрементный ID
    commander_id = db.Column(db.Integer, db.ForeignKey('commanders.id'))
    rank_id = db.Column(db.Integer, db.ForeignKey('military_ranks.id'))
    date_promoted = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    
    # Явно указываем foreign_keys для отношений
    commander = db.relationship('Commander', back_populates='rank_assignments', foreign_keys=[commander_id])
    rank = db.relationship('MilitaryRank', back_populates='assignments', foreign_keys=[rank_id])

    __table_args__ = (db.UniqueConstraint('commander_id', 'rank_id', 'date_promoted', name='uq_commander_rank_date'),)

class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    event = db.Column(db.String(5000))
    place_id = db.Column(db.Integer, db.ForeignKey('places.id'))
    notes = db.Column(db.String(5000))

    place = db.relationship('Place', back_populates='events')
