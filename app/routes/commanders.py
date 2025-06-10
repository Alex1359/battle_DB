from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app.models import Commander, Country, MilitaryRank
from app import db
from marshmallow import Schema, fields, validate, ValidationError, validates
from datetime import datetime
from app.services.commander_service import CommanderService

bp = Blueprint('commanders', __name__, url_prefix='/commanders')

class CommanderSchema(Schema):
    id = fields.Int(dump_only=True)
    first_name = fields.Str(required=True)
    last_name = fields.Str(required=True)
    birth_date = fields.Date(allow_none=True)
    death_date = fields.Date(allow_none=True)
    biography = fields.Str(allow_none=True)
    country_id = fields.Int(required=True, data_key="nationally_id")  # Связываем с моделью
    rank_id = fields.Int(allow_none=True)

    @validates('death_date')
    def validate_death_date(self, value, **kwargs):
        if not value:
            return
        if value > datetime.now().date():
            raise ValidationError("Дата смерти не может быть в будущем")
        if 'birth_date' in self.context and self.context['birth_date'] and value < self.context['birth_date']:
            raise ValidationError("Дата смерти должна быть после даты рождения")
        
# Список всех командующих
@bp.route('/', methods=['GET'])
def list_commanders():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    commanders = Commander.query.order_by(
        Commander.last_name,
        Commander.first_name
    ).paginate(page=page, per_page=per_page)
    
    return render_template('commanders/list.html', commanders=commanders)

# Форма добавления нового командующего
@bp.route('/new', methods=['GET', 'POST'])
def new_commander():
    form_data = request.form if request.method == 'POST' else None
    countries = Country.query.order_by(Country.name).all()
    
    if request.method == 'POST':
        schema = CommanderSchema()
        try:
            # Подготовка данных
            data = {
                'first_name': request.form.get('first_name'),
                'last_name': request.form.get('last_name'),
                'birth_date': request.form.get('birth_date') or None,
                'death_date': request.form.get('death_date') or None,
                'biography': request.form.get('biography'),
                'nationally_id': request.form.get('country_id'),  # Преобразуем country_id в nationally_id
                'rank_id': request.form.get('rank_id') or None
            }
            
            # Конвертация дат
            context = {}
            if data['birth_date']:
                data['birth_date'] = datetime.strptime(data['birth_date'], '%Y-%m-%d').date()
                context['birth_date'] = data['birth_date']
            if data['death_date']:
                data['death_date'] = datetime.strptime(data['death_date'], '%Y-%m-%d').date()
            
            # Валидация
            validated_data = schema.load(data, context=context)
            
            # Создание командира
            commander = Commander(**validated_data)
            db.session.add(commander)
            db.session.commit()
            
            flash('Командующий успешно добавлен', 'success')
            return redirect(url_for('commanders.list_commanders'))
            
        except ValidationError as e:
            db.session.rollback()
            flash(f'Ошибка валидации: {str(e.messages)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при сохранении: {str(e)}', 'danger')
    
    # Получаем звания если уже выбрана страна
    ranks = []
    if form_data and form_data.get('country_id'):
        ranks = MilitaryRank.query.filter_by(country_id=form_data['country_id']).order_by(MilitaryRank.name).all()
    
    return render_template('commanders/new.html',
                         form_data=form_data,
                         countries=countries,
                         ranks=ranks)

# Просмотр информации о командующем
@bp.route('/<int:id>', methods=['GET'])
def view_commander(id):
    commander = Commander.query.get_or_404(id)
    return render_template('commanders/view.html', commander=commander)

# Редактирование командующего
@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_commander(id):
    commander = Commander.query.get_or_404(id)
    
    if request.method == 'POST':
        schema = CommanderSchema()
        try:
            data = schema.load(request.form)
            form_data = request.form.to_dict()
            for date_field in ['birth_date', 'death_date']:
                if not form_data.get(date_field):
                    form_data[date_field] = None
            
            data = schema.load(form_data, context={'birth_date': form_data.get('birth_date')})

            commander.first_name = data['first_name']
            commander.last_name = data['last_name']
            commander.birth_date = data.get('birth_date')
            commander.death_date = data.get('death_date')
            commander.biography = data.get('biography')
            commander.country_id = data['country_id']
            commander.rank_id = data.get('rank_id')
            
            db.session.commit()
            flash('Изменения сохранены', 'success')
            return redirect(url_for('commanders.view_commander', id=commander.id))
            
        except ValidationError as e:
            db.session.rollback()
            flash(f'Ошибка валидации: {e.messages}', 'danger')

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при сохранении изменений: {str(e)}', 'danger')
    
    countries = Country.query.order_by(Country.name).all()
    ranks = MilitaryRank.query.filter_by(country_id=commander.country_id).order_by(MilitaryRank.rank_level).all()
    
    return render_template('commanders/edit.html', 
                         commander=commander,
                         countries=countries,
                         ranks=ranks)

# Удаление командующего
@bp.route('/<int:id>/delete', methods=['POST'])
def delete_commander(id):
    commander = Commander.query.get_or_404(id)
    
    try:
        db.session.delete(commander)
        db.session.commit()
        flash('Командующий успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении командующего: {str(e)}', 'danger')
    
    return redirect(url_for('commanders.list_commanders'))

# API: Получение званий по стране (для AJAX)
@bp.route('/api/ranks', methods=['GET'])
def get_ranks_api():
    country_id = request.args.get('country_id', type=int)
    if not country_id:
        return jsonify([])
    
    ranks = MilitaryRank.query.filter_by(country_id=country_id).order_by(MilitaryRank.name).all()
    return jsonify([{'id': r.id, 'name': r.name} for r in ranks])

# API: Поиск командующих (для автодополнения)
@bp.route('/api/search', methods=['GET'])
def search_commanders():
    query = request.args.get('query', '')
    
    if len(query) < 2:
        return jsonify([])
    
    commanders = Commander.query.filter(
        (Commander.last_name.ilike(f'%{query}%')) |
        (Commander.first_name.ilike(f'%{query}%'))
    ).limit(10).all()
    
    return jsonify([{
        'id': c.id,
        'name': f'{c.last_name} {c.first_name}',
        'country': c.country.name if c.country else ''
    } for c in commanders])

def detail(commander_id):
    commander = CommanderService.get_commander_with_ranks(commander_id)
    ranks = MilitaryRank.query.order_by(MilitaryRank.rank_level).all()
    return render_template('commanders/detail.html',
                         commander=commander,
                         available_ranks=ranks)

@bp.route('/<int:commander_id>/add_rank', methods=['POST'])
def add_rank(commander_id):
    rank_id = request.form.get('rank_id')
    promotion_date = request.form.get('promotion_date')
    
    try:
        CommanderService.add_rank_to_commander(commander_id, rank_id, promotion_date)
        flash('Звание успешно добавлено', 'success')
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('commanders.detail', commander_id=commander_id))