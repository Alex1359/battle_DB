from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app.models import MilitaryUnit, Country, Commander
from app import db
from marshmallow import Schema, ValidationError, fields, validate, validates
from datetime import datetime

bp = Blueprint('units', __name__, url_prefix='/units')

class UnitSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    formation_date = fields.Date(allow_none=True)
    dissolution_date = fields.Date(allow_none=True)
    country_id = fields.Int(required=True)
    parent_unit_id = fields.Int(allow_none=True)
    commander_id = fields.Int(allow_none=True)

    @validates('dissolution_date')
    def validate_dates(self, value, data, **kwargs):
        if 'formation_date' in data and value and data['formation_date']:
            if value < data['formation_date']:
                raise ValidationError('Дата расформирования не может быть раньше даты формирования')

# Список всех подразделений
@bp.route('/', methods=['GET'])
def list_units():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    units = MilitaryUnit.query.order_by(
        MilitaryUnit.name
    ).paginate(page=page, per_page=per_page)
    
    return render_template('units/list.html', units=units)

# Форма добавления нового подразделения
@bp.route('/new', methods=['GET', 'POST'])
def new_unit():
    if request.method == 'POST':
        schema = UnitSchema()
        try:
            data = schema.load(request.form)
            
            unit = MilitaryUnit(
                name=data['name'],
                formation_date=data.get('formation_date'),
                dissolution_date=data.get('dissolution_date'),
                country_id=data['country_id'],
                parent_unit_id=data.get('parent_unit_id'),
                commander_id=data.get('commander_id')
            )
            
            db.session.add(unit)
            db.session.commit()
            flash('Подразделение успешно добавлено', 'success')
            return redirect(url_for('units.list_units'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении подразделения: {str(e)}', 'danger')
    
    countries = Country.query.order_by(Country.name).all()
    commanders = Commander.query.order_by(Commander.last_name, Commander.first_name).all()
    
    return render_template('units/new.html', 
                         countries=countries,
                         commanders=commanders)

# Просмотр информации о подразделении
@bp.route('/<int:id>', methods=['GET'])
def view_unit(id):
    unit = MilitaryUnit.query.get_or_404(id)
    subunits = MilitaryUnit.query.filter_by(parent_unit_id=id).all()
    return render_template('units/view.html', unit=unit, subunits=subunits)

# Редактирование подразделения
@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_unit(id):
    unit = MilitaryUnit.query.get_or_404(id)
    
    if request.method == 'POST':
        schema = UnitSchema()
        try:
            data = schema.load(request.form)
            
            unit.name = data['name']
            unit.formation_date = data.get('formation_date')
            unit.dissolution_date = data.get('dissolution_date')
            unit.country_id = data['country_id']
            unit.parent_unit_id = data.get('parent_unit_id')
            unit.commander_id = data.get('commander_id')
            
            db.session.commit()
            flash('Изменения сохранены', 'success')
            return redirect(url_for('units.view_unit', id=unit.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при сохранении изменений: {str(e)}', 'danger')
    
    countries = Country.query.order_by(Country.name).all()
    commanders = Commander.query.order_by(Commander.last_name, Commander.first_name).all()
    units = MilitaryUnit.query.filter(
        MilitaryUnit.id != id,  # Исключаем текущее подразделение из списка возможных родителей
        MilitaryUnit.country_id == unit.country_id  # Только подразделения той же страны
    ).all()
    
    return render_template('units/edit.html', 
                         unit=unit,
                         countries=countries,
                         commanders=commanders,
                         units=units)

# Удаление подразделения
@bp.route('/<int:id>/delete', methods=['POST'])
def delete_unit(id):
    unit = MilitaryUnit.query.get_or_404(id)
    
    try:
        # Перед удалением обнуляем parent_unit_id у дочерних подразделений
        MilitaryUnit.query.filter_by(parent_unit_id=id).update({'parent_unit_id': None})
        db.session.delete(unit)
        db.session.commit()
        flash('Подразделение успешно удалено', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении подразделения: {str(e)}', 'danger')
    
    return redirect(url_for('units.list_units'))

# API: Получение подразделений по стране (для AJAX)
@bp.route('/api/units_by_country', methods=['GET'])
def get_units_by_country():
    country_id = request.args.get('country_id')
    if not country_id:
        return jsonify({'error': 'Не указан country_id'}), 400
    
    units = MilitaryUnit.query.filter_by(country_id=country_id).order_by(MilitaryUnit.name).all()
    return jsonify([{'id': u.id, 'name': u.name} for u in units])

# API: Получение командующих по стране (для AJAX)
@bp.route('/api/commanders_by_country', methods=['GET'])
def get_commanders_by_country():
    country_id = request.args.get('country_id')
    if not country_id:
        return jsonify({'error': 'Не указан country_id'}), 400
    
    commanders = Commander.query.filter_by(country_id=country_id)\
        .order_by(Commander.last_name, Commander.first_name).all()
    return jsonify([{'id': c.id, 'name': f'{c.last_name} {c.first_name}'} for c in commanders])