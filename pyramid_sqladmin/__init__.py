from pyramid.httpexceptions import HTTPFound
from pyramid.security import Allow, Everyone
from pyramid.view import view_config
from sqlalchemy.orm.mapper import _mapper_registry
import transaction
import tw2.sqla as tws
import tw2.core as twc
import inspect
import os


_marker = object()
AVAILABLE_OBJECTS = _marker

def get_mapped_classes():
    """Get all the SQLAlchemy mapped classes
    """
    global AVAILABLE_OBJECTS
    if AVAILABLE_OBJECTS is not _marker:
        return AVAILABLE_OBJECTS

    AVAILABLE_OBJECTS = {}
    for m in _mapper_registry:
        AVAILABLE_OBJECTS[m.class_.__name__.lower()] = m.class_
    return AVAILABLE_OBJECTS


def get_class(class_name):
    """Get the class according to the given class name.
    """
    classes = get_mapped_classes()
    return classes.get(class_name)


# Request helpers
def get_obj(info):
    """Get the object corresponding to the request
    """
    class_name = info['match']['classname']
    ident = info['match']['id']
    if not class_name or not ident:
        return None
    cls = get_class(class_name)
    if not cls:
        return None
    obj = cls.query.get(ident)
    return obj


def exist_object(info, request):
    """Validate the object found from the request exist

    note:: We set cls_or_obj to the match dict with the found object to avoid
    to make a second SQL query later.
    """
    obj = get_obj(info)
    if not obj:
        return False

    info['match']['cls_or_obj'] = obj
    return True


def exist_class(info, request):
    """Validate the class found from the request exist

    note:: We set cls_or_obj to the match dict with the found class to be
    coherent with :function `exist_object`
    """
    classname = info['match']['classname']
    cls = get_class(classname)
    if not cls:
        return False

    info['match']['cls_or_obj'] = cls
    return True



# We need an object to set the permission for the sqladmin home page
class HomeFactory(object): pass


def admin_factory(request):
    """Set the admin permission on the found obj or cls
    """
    acl = get_setting(request.registry.settings, 'acl')
    cls_or_obj = request.matchdict.get('cls_or_obj')
    cls_or_obj = cls_or_obj or HomeFactory()
    cls_or_obj.__acl__ = [(Allow, acl, 'sqladmin')]
    return cls_or_obj



# Views
@view_config(
    route_name='admin_home',
    permission='sqladmin',
    renderer='sqladmin/home.mak')
def home(request):
    """Display all the editable classes
    """
    links = []
    for name, cls in get_mapped_classes().items():
        links += [(cls.__name__, request.route_url('admin_list', classname=name))]
    return {'links': links}


@view_config(
    route_name='admin_list',
    permission='sqladmin',
    renderer='sqladmin/default.mak')
def admin_list(context, request):
    """Display all the objects in the DB for a given class.
    """
    return {
        'html': context.view_all(),
    }


@view_config(
    route_name='admin_edit',
    permission='sqladmin',
    renderer='sqladmin/default.mak')
@view_config(
    route_name='admin_new',
    permission='sqladmin',
    renderer='sqladmin/default.mak')
def add_or_update(context, request):
    """Add or update a DB object.
    """
    context_is_obj = not inspect.isclass(context)
    widget = context.edit_form()
    if request.method == 'POST':
        try:
            data = widget.validate(request.POST)
            cls = context
            if context_is_obj:
                # Add the primary key value to make sure we will update the
                # object
                data[context._pk_name()] = context.pk_id
                cls = type(context)
            obj = tws.utils.update_or_create(cls, data)
            transaction.commit()
            # The new object should be bound to the current session
            obj.db_session_add()
            redirect_url = request.route_url(
                'admin_edit',
                classname=cls.__name__.lower(),
                id=obj.pk_id,
            )
            return HTTPFound(location=redirect_url)
        except twc.ValidationError, e:
            widget = e.widget

    elif context_is_obj:
        widget.value = context

    return {
        'html': widget.display(),
    }


SETTINGS_PREFIX = 'sqladmin.'


def security_parser(value):
    if value == 'Everyone':
        return Everyone
    return value


default_settings = (
    ('route_prefix', str, '/admin'),
    ('acl', security_parser, 'sqladmin'),
    )


def parse_settings(settings):
    parsed = {}
    def populate(name, convert, default):
        name = '%s%s' % (SETTINGS_PREFIX, name)
        value = convert(settings.get(name, default))
        parsed[name] = value
    for name, convert, default in default_settings:
        populate(name, convert, default)
    return parsed


def get_setting(settings, name):
    name = '%s%s' % (SETTINGS_PREFIX, name)
    return settings.get(name)


def includeme(config):

    settings = parse_settings(config.registry.settings)
    config.registry.settings.update(settings)

    if not 'mako.directories' in config.registry.settings:
        config.registry.settings['mako.directories'] = []
    sqladmin_dir = 'pyramid_sqladmin:templates'
    if type(config.registry.settings['mako.directories']) is list:
        config.registry.settings['mako.directories'] += [sqladmin_dir]
    else:
        config.registry.settings['mako.directories'] += '\n%s' % sqladmin_dir

    route_prefix = get_setting(settings, 'route_prefix')
    assert route_prefix.startswith('/'), ('The route_prefix %s is not valid.'
         ' It should start with a /') % route_prefix

    config.add_route(
        'admin_home',
        route_prefix,
        factory=admin_factory,
    )
    config.add_route(
        'admin_list',
        os.path.join(route_prefix, '{classname}'),
        factory=admin_factory,
        custom_predicates=(exist_class,),
    )
    config.add_route(
        'admin_new',
        os.path.join(route_prefix, '{classname}', 'new'),
        factory=admin_factory,
        custom_predicates=(exist_class,),
    )
    config.add_route(
        "admin_edit",
        os.path.join(route_prefix, '{classname}', '{id}', 'edit'),
        factory=admin_factory,
        custom_predicates=(exist_object,),
    )
    config.scan()

    # Set edit link on all the SQLAlchemy objects
    for classname, cls in get_mapped_classes().items():
        if not hasattr(cls, 'tws_edit_link'):
            link = os.path.join(route_prefix, classname, '$', 'edit')
            cls.tws_edit_link = link

