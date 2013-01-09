from pyramid.httpexceptions import HTTPFound
from pyramid.security import Allow
from pyramid.view import view_config
from sqlalchemy.orm.mapper import _mapper_registry
import transaction
import tw2.sqla as tws
import tw2.core as twc
import inspect


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


def admin_factory(request):
    """Set the admin permission on the found obj or cls
    """
    cls_or_obj = request.matchdict['cls_or_obj']
    cls_or_obj.__acl__ = [(Allow, 'role:admin', 'admin')]
    return cls_or_obj



# Views
@view_config(
    route_name='admin_home',
    renderer='pyramid_sqladmin:templates/home.mak')
def home(request):
    """Display all the editable classes
    """
    links = []
    for name, cls in get_mapped_classes().items():
        links += [(cls.__name__, request.route_url('admin_list', classname=name))]
    return {'links': links}


@view_config(
    route_name='admin_list',
    renderer='pyramid_sqladmin:templates/default.mak')
def admin_list(context, request):
    """Display all the objects in the DB for a given class.
    """
    return {
        'html': context.view_all(),
    }


@view_config(
    route_name='admin_edit',
    renderer='pyramid_sqladmin:templates/default.mak')
@view_config(
    route_name='admin_new',
    renderer='pyramid_sqladmin:templates/default.mak')
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



def includeme(config):
    config.add_route(
        'admin_home',
        '/admin',
    )
    config.add_route(
        'admin_list',
        '/admin/{classname}',
        factory=admin_factory,
        custom_predicates=(exist_class,),
    )
    config.add_route(
        'admin_new',
        '/admin/{classname}/new',
        factory=admin_factory,
        custom_predicates=(exist_class,),
    )
    config.add_route(
        "admin_edit",
        '/admin/{classname}/{id}/edit',
        factory=admin_factory,
        custom_predicates=(exist_object,),
    )
    config.scan()
