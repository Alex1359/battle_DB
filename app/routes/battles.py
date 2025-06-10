from flask import Blueprint, current_app, json, render_template, request, jsonify, redirect, url_for, flash, session
from app.models import Battle, Battleparticipations, Country, MilitaryUnit, Commander, Place, Trophy, BattleLoss
from app import db
from marshmallow import Schema, ValidationError, fields, validate, validates
from datetime import datetime, time
from sqlalchemy import and_, func
from geoalchemy2.functions import ST_AsGeoJSON
from datetime import datetime, time
from dateutil import parser


bp = Blueprint('battles', __name__, url_prefix='/battles')

class BattleSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=3, max=100))
    date_begin = fields.Date(required=True)
    date_end = fields.Date(allow_none=True)
    description = fields.Str(allow_none=True)
    place_id = fields.Int(allow_none=True)

    @validates('date_end')
    def validate_dates(self, value, data, **kwargs):
        if value and 'date_begin' in data and data['date_begin']:
            if value < data['date_begin']:
                raise ValidationError('Дата окончания не может быть раньше даты начала')

class participationsSchema(Schema):
    side = fields.Str(required=True, validate=validate.OneOf(['allies', 'axis', 'other']))
    unit_id = fields.Int(required=True)
    commander_id = fields.Int(allow_none=True)
    is_victor = fields.Bool(load_default=False)

class LossSchema(Schema):
    type = fields.Str(required=True, validate=validate.OneOf(['killed', 'wounded', 'captured']))
    count = fields.Int(required=True, validate=validate.Range(min=1))

class TrophySchema(Schema):
    type = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    quantity = fields.Int(validate=validate.Range(min=1), load_default=1)
    captor_id = fields.Int(required=True)

# Список всех сражений
@bp.route('/')
def list_battles():
    battles = db.session.query(
        Battle.id,
        Battle.name,
        Battle.date_begin,
        Battle.date_end,
        Battle.victory,
        Place.name.label('place_name'),
        func.ST_AsGeoJSON(Place.geom).label('geom_json')
    ).join(Place).all()
    
    battles_data = []
    for battle in battles:
        # Безопасное преобразование даты для исторических дат
        timestamp = 0
        date_str = None
        
        if battle.date_begin:
            try:
                # Преобразуем в строку и обратно для унификации
                date_str = battle.date_begin.strftime('%Y-%m-%d')
                dt = parser.parse(date_str)
                # Альтернативный метод расчета timestamp
                timestamp = (dt - datetime(1970, 1, 1)).total_seconds()
            except Exception as e:
                current_app.logger.error(f"Error processing date for battle {battle.id}: {str(e)}")
                timestamp = 0
        
        battles_data.append({
            'id': battle.id,
            'name': battle.name,
            'date': date_str if date_str else None,
            'timestamp': int(timestamp),
            'victory': battle.victory,
            'place_name': battle.place_name,
            'geom': json.loads(battle.geom_json) if battle.geom_json else None
        })
    
    return render_template('battles/list.html', battles=battles_data)

# Многошаговая форма добавления сражения
@bp.route('/new', methods=['GET', 'POST'])
def new_battle():
    if request.method == 'GET':
        # Инициализация сессии для нового сражения
        session.pop('battle_data', None)
        session.pop('participations_data', None)
        session.pop('losses_data', None)
        session.pop('trophies_data', None)
        
        countries = Country.query.order_by(Country.name).all()
        places = Place.query.order_by(Place.name).all()
        
        return render_template('battles/wizard_step1.html',
                             countries=countries,
                             places=places)
    
    # Обработка шага 1 (основная информация)
    if request.form.get('step') == '1':
        schema = BattleSchema()
        try:
            battle_data = schema.load(request.form)
            session['battle_data'] = battle_data
            return redirect(url_for('battles.new_battle_step2'))
        except Exception as e:
            flash(f'Ошибка валидации: {str(e)}', 'danger')
            return redirect(url_for('battles.new_battle'))

@bp.route('/new/step2', methods=['GET', 'POST'])
def new_battle_step2():
    if 'battle_data' not in session:
        return redirect(url_for('battles.new_battle'))
    
    if request.method == 'GET':
        battle_data = session['battle_data']
        participationss = session.get('participations_data', [])
        
        # Получаем только подразделения стран, участвующих в сражении
        # (в реальном приложении нужно определить страны участников)
        units = MilitaryUnit.query.order_by(MilitaryUnit.name).all()
        commanders = Commander.query.order_by(Commander.last_name, Commander.first_name).all()
        
        return render_template('battles/wizard_step2.html',
                             battle=battle_data,
                             participationss=participationss,
                             units=units,
                             commanders=commanders)
    
    # Обработка шага 2 (участники)
    if request.form.get('step') == '2':
        try:
            participationss = []
            participations_schema = participationsSchema()
            
            # Обработка каждого участника
            i = 0
            while f'participations-{i}-side' in request.form:
                participations_data = {
                    'side': request.form[f'participations-{i}-side'],
                    'unit_id': request.form[f'participations-{i}-unit_id'],
                    'commander_id': request.form.get(f'participations-{i}-commander_id'),
                    'is_victor': request.form.get(f'participatiions-{i}-is_victor') == 'on'
                }
                
                participations = participations_schema.load(participations_data)
                participationss.append(participations)
                i += 1
            
            session['participationss_data'] = participationss
            return redirect(url_for('battles.new_battle_step3'))
            
        except Exception as e:
            flash(f'Ошибка валидации участников: {str(e)}', 'danger')
            return redirect(url_for('battles.new_battle_step2'))

@bp.route('/new/step3', methods=['GET', 'POST'])
def new_battle_step3():
    if 'battle_data' not in session or 'participationss_data' not in session:
        return redirect(url_for('battles.new_battle'))
    
    if request.method == 'GET':
        battle_data = session['battle_data']
        participationss = session['participationss_data']
        trophies = session.get('trophies_data', [])
        
        # Подготовка данных для формы потерь
        losses_data = []
        for i, participations in enumerate(participationss):
            unit = MilitaryUnit.query.get(participations['unit_id'])
            losses_data.append({
                'unit_id': participations['unit_id'],
                'unit_name': unit.name if unit else 'Unknown',
                'losses': []
            })
        
        return render_template('battles/wizard_step3.html',
                             battle=battle_data,
                             participationss=participationss,
                             losses_data=losses_data,
                             trophies=trophies)
    
    # Обработка шага 3 (потери и трофеи)
    if request.form.get('step') == '3':
        try:
            # Обработка потерь
            loss_schema = LossSchema()
            losses = []
            
            i = 0
            while f'losses-{i}-type' in request.form:
                loss_data = {
                    'type': request.form[f'losses-{i}-type'],
                    'count': request.form[f'losses-{i}-count'],
                    'participations_id': request.form[f'losses-{i}-participations_id']
                }
                
                loss = loss_schema.load(loss_data)
                losses.append(loss)
                i += 1
            
            session['losses_data'] = losses
            
            # Обработка трофеев
            trophy_schema = TrophySchema()
            trophies = []
            
            i = 0
            while f'trophies-{i}-type' in request.form:
                trophy_data = {
                    'type': request.form[f'trophies-{i}-type'],
                    'description': request.form.get(f'trophies-{i}-description'),
                    'quantity': request.form.get(f'trophies-{i}-quantity', 1),
                    'captor_id': request.form[f'trophies-{i}-captor_id']
                }
                
                trophy = trophy_schema.load(trophy_data)
                trophies.append(trophy)
                i += 1
            
            session['trophies_data'] = trophies
            
            # Сохранение всего сражения в БД
            return save_complete_battle()
            
        except Exception as e:
            flash(f'Ошибка валидации: {str(e)}', 'danger')
            return redirect(url_for('battles.new_battle_step3'))

def save_complete_battle():
    try:
        # Создаем сражение
        battle_schema = BattleSchema()
        battle_data = battle_schema.load(session['battle_data'])
        
        battle = Battle(**battle_data)
        db.session.add(battle)
        db.session.flush()  # Получаем ID сражения
        
        # Добавляем участников
        participations_schema = participationsSchema()
        for participations_data in session['participationss_data']:
            participations = Battleparticipations(
                battle_id=battle.id,
                **participations_schema.load(participations_data)
            )
            db.session.add(participations)
            db.session.flush()  # Получаем ID участника
            
            # Добавляем потери для этого участника
            loss_schema = LossSchema()
            for loss_data in session.get('losses_data', []):
                if str(loss_data.get('participations_id')) == str(participations_data.get('unit_id')):
                    loss = BattleLoss(
                        participations_id=participations.id,
                        **loss_schema.load(loss_data)
                    )
                    db.session.add(loss)
        
        # Добавляем трофеи
        trophy_schema = TrophySchema()
        for trophy_data in session.get('trophies_data', []):
            trophy = Trophy(
                battle_id=battle.id,
                **trophy_schema.load(trophy_data)
            )
            db.session.add(trophy)
        
        db.session.commit()
        
        # Очищаем сессию
        session.pop('battle_data', None)
        session.pop('participationss_data', None)
        session.pop('losses_data', None)
        session.pop('trophies_data', None)
        
        flash('Сражение успешно сохранено', 'success')
        return redirect(url_for('battles.view_battle', id=battle.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при сохранении сражения: {str(e)}', 'danger')
        return redirect(url_for('battles.new_battle_step3'))

# Просмотр информации о сражении
@bp.route('/<int:id>', methods=['GET'])
def view_battle(id):
    battle = Battle.query.get_or_404(id)
    participationss = Battleparticipations.query.filter_by(battle_id=id).all()
    
    # Группировка потерь по участникам
    losses = {}
    for participations in participationss:
        participations_losses = BattleLoss.query.filter_by(participations_id=participations.id).all()
        losses[participations.id] = participations_losses
    
    trophies = Trophy.query.filter_by(battle_id=id).all()
    
    return render_template('battles/view.html',
                         battle=battle,
                         participationss=participationss,
                         losses=losses,
                         trophies=trophies)

# Редактирование сражения (упрощенная версия)
@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_battle(id):
    battle = Battle.query.get_or_404(id)
    
    if request.method == 'POST':
        schema = BattleSchema()
        try:
            data = schema.load(request.form)
            
            battle.name = data['name']
            battle.date_begin = data['date_begin']
            battle.date_end = data.get('date_end')
            battle.description = data.get('description')
            battle.place_id = data.get('place_id')
            
            db.session.commit()
            flash('Изменения сохранены', 'success')
            return redirect(url_for('battles.view_battle', id=battle.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при сохранении изменений: {str(e)}', 'danger')
    
    places = Place.query.order_by(Place.name).all()
    return render_template('battles/edit.html',
                         battle=battle,
                         places=places)

# Удаление сражения
@bp.route('/<int:id>/delete', methods=['POST'])
def delete_battle(id):
    battle = Battle.query.get_or_404(id)
    
    try:
        # Удаляем связанные данные
        Battleparticipations.query.filter_by(battle_id=id).delete()
        Trophy.query.filter_by(battle_id=id).delete()
        
        db.session.delete(battle)
        db.session.commit()
        flash('Сражение успешно удалено', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении сражения: {str(e)}', 'danger')
    
    return redirect(url_for('battles.list_battles'))

# API: Поиск мест (для автодополнения)
@bp.route('/api/search_places', methods=['GET'])
def search_places():
    query = request.args.get('query', '')
    
    if len(query) < 2:
        return jsonify([])
    
    places = Place.query.filter(Place.name.ilike(f'%{query}%')).limit(10).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'coordinates': f"{p.latitude}, {p.longitude}" if p.latitude and p.longitude else ''
    } for p in places])