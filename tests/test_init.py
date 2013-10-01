import unittest
from webtest import TestApp
from pyramid.config import Configurator
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from pyramid import testing
from pyramid.security import remember, forget, Everyone
import sqlalchemy as sa
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    clear_mappers,
    )
from zope.sqlalchemy import ZopeTransactionExtension
from sqla_declarative.declarative import extended_declarative_base
import transaction
import pyramid_sqladmin as pysqla
import tw2.core as twc
import tw2.core.testbase as tw2test


class TestInit(unittest.TestCase):

    def get_dummy_request(self):
        request = testing.DummyRequest()
        request.registry.settings = {'sqladmin.acl': 'sqladmin'}
        return request

    def setUp(self):
        clear_mappers()
        pysqla.AVAILABLE_OBJECTS = pysqla._marker
        self.session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
        Base = extended_declarative_base(
            self.session,
            metadata=sa.MetaData('sqlite:///:memory:'))

        class Test1(Base):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(50))

        class Test2(Base):
            idtest = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(50))

        Base.metadata.create_all()

        self.Test1 = Test1
        self.Test2 = Test2
        with transaction.manager:
            self.value1 = Test1(name='Bob')
            self.session.add(self.value1)
            self.value2 = Test2(name='Bob')
            self.session.add(self.value2)

    def tearDown(self):
        transaction.abort()

    def test_get_mapped_classes(self):
        result = pysqla.get_mapped_classes()
        self.assertEqual(len(result), 2)
        self.assertEqual(result['test1'], self.Test1)
        self.assertEqual(result['test2'], self.Test2)

    def test_get_class(self):
        self.assertEqual(pysqla.get_class('unexisting'), None)
        self.assertEqual(pysqla.get_class('test1'), self.Test1)

    def test_get_obj(self):
        info = {'match': {
            'classname': '',
            'id': '',
            }}
        result = pysqla.get_obj(info)
        self.assertEqual(result, None)

        info = {'match': {
            'classname': 'test1',
            'id': 1,
            }}
        result = pysqla.get_obj(info)
        obj = self.Test1.query.get(1)
        self.assertEqual(result, obj)

        info = {'match': {
            'classname': 'test1',
            'id': 10,
            }}
        result = pysqla.get_obj(info)
        self.assertEqual(result, None)

        info = {'match': {
            'classname': 'unexisting',
            'id': 1,
            }}
        result = pysqla.get_obj(info)
        self.assertEqual(result, None)

    def test_exist_object(self):
        info = {'match': {
            'classname': 'unexisting',
            'id': 1,
            }}
        self.assertEqual(pysqla.exist_object(info, None), False)

        info = {'match': {
            'classname': 'test1',
            'id': 1,
            }}
        self.assertEqual(pysqla.exist_object(info, None), True)
        obj = self.Test1.query.get(1)
        self.assertEqual(info['match']['cls_or_obj'], obj)

    def test_exist_class(self):
        info = {'match': {
            'classname': 'unexisting',
            }}
        self.assertEqual(pysqla.exist_class(info, None), False)

        info = {'match': {
            'classname': 'test1',
            }}
        self.assertEqual(pysqla.exist_class(info, None), True)
        self.assertEqual(info['match']['cls_or_obj'], self.Test1)

    def test_admin_factory(self):
        request = self.get_dummy_request()
        cls = pysqla.admin_factory(request)
        self.assertEqual(cls.__acl__, [('Allow', 'sqladmin', 'sqladmin')])

        request.matchdict['cls_or_obj'] = self.Test1
        cls = pysqla.admin_factory(request)
        self.assertEqual(cls.__acl__, [('Allow', 'sqladmin', 'sqladmin')])

    def test_home(self):
        request = testing.DummyRequest()
        request.route_url = lambda *args, **kw: 'http://server/%s' % kw['classname']
        response = pysqla.home(request)
        expected = {
            'links': [('Test1', 'http://server/test1'),
                      ('Test2', 'http://server/test2')]
        }
        self.assertEqual(response, expected)

    def test_admin_list(self):
        request = testing.DummyRequest()
        self.Test1.view_all = classmethod(lambda *args, **kw: 'view all')
        response = pysqla.admin_list(self.Test1, request)
        expected = {'html': 'view all'}
        self.assertEqual(response, expected)

    def test_GET_add_or_update(self):
        class MockForm(object):
            value = None
            def display(self):
                s = 'display form'
                if self.value:
                    s += ' with some values'
                return s

        request = testing.DummyRequest()
        self.Test1.edit_form = classmethod(lambda *args, **kw: MockForm())
        response = pysqla.add_or_update(self.Test1, request)
        expected = {'html': 'display form'}
        self.assertEqual(response, expected)

        response = pysqla.add_or_update(self.Test1.query.get(1), request)
        expected = {'html': 'display form with some values'}
        self.assertEqual(response, expected)

    def test_POST_add_or_update(self):
        class MockForm(object):
            value = None
            def display(self):
                s = 'display form'
                if self.value:
                    s += ' with some values'
                return s
            def validate(self, data):
                return data

        request = testing.DummyRequest()
        request.route_url = lambda *args, **kw: (
            'http://server/%s/%s' % (kw['classname'], kw['id']))
        request.POST = {'name': 'Fred'}
        request.method = 'POST'
        self.Test1.edit_form = classmethod(lambda *args, **kw: MockForm())
        response = pysqla.add_or_update(self.Test1, request)
        self.assertEqual(response.status, '302 Found')
        self.assertTrue(
            ('Location',
            'http://server/test1/2')
            in response._headerlist)
        self.assertEqual(self.Test1.query.get(1).name, 'Bob')
        self.assertEqual(self.Test1.query.get(2).name, 'Fred')

        response = pysqla.add_or_update(self.Test1.query.get(1), request)
        self.assertEqual(response.status, '302 Found')
        self.assertTrue(
            ('Location',
            'http://server/test1/1')
            in response._headerlist)
        self.assertEqual(self.Test1.query.get(1).name, 'Fred')
        self.assertEqual(self.Test1.query.count(), 2)

    def test_fail_POST_add_or_update(self):
        class MockForm(object):
            value = None
            def display(self):
                s = 'display form'
                if self.value:
                    s += ' with some values'
                return s
            def validate(self, data):
                raise twc.ValidationError('Validation error', widget=self)

        request = testing.DummyRequest()
        request.POST = {'name': 'Fred'}
        request.method = 'POST'
        form = MockForm()
        self.Test1.edit_form = classmethod(lambda *args, **kw: form)
        response = pysqla.add_or_update(self.Test1, request)
        expected = {'html': 'display form'}
        self.assertEqual(response, expected)

        form.value = request.POST
        response = pysqla.add_or_update(self.Test1.query.get(1), request)
        expected = {'html': 'display form with some values'}
        self.assertEqual(response, expected)
        self.assertEqual(self.Test1.query.get(1).name, 'Bob')

    def test_parse_settings(self):
        settings = {}
        result = pysqla.parse_settings(settings)
        expected = {
            'sqladmin.route_prefix': '/admin',
            'sqladmin.acl': 'sqladmin'}
        self.assertEqual(result, expected)

        settings = {
            'sqladmin.route_prefix': '/backoffice'}
        result = pysqla.parse_settings(settings)
        expected = {
            'sqladmin.route_prefix': '/backoffice',
            'sqladmin.acl': 'sqladmin'}
        self.assertEqual(result, expected)

    def test_get_setting(self):
        settings = {
            'sqladmin.route_prefix': '/admin',
            'sqladmin.acl': 'sqladmin'}

        result = pysqla.get_setting(settings, 'route_prefix')
        self.assertEqual(result, '/admin')

    def test_security_parser(self):
        result = pysqla.security_parser('role:admin')
        self.assertEqual(result, 'role:admin')
        result = pysqla.security_parser('Everyone')
        self.assertEqual(result, Everyone)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        clear_mappers()
        pysqla.AVAILABLE_OBJECTS = pysqla._marker
        self.config = testing.setUp()
        self.config.include('pyramid_sqladmin')

    def tearDown(self):
        testing.tearDown()

    def test_url(self):
        request = testing.DummyRequest()
        url = request.route_url('admin_home')
        expected = 'http://example.com/admin'
        self.assertEqual(url, expected)

        url = request.route_url('admin_list', classname='test1')
        expected = 'http://example.com/admin/test1'
        self.assertEqual(url, expected)

        url = request.route_url('admin_new', classname='test1')
        expected = 'http://example.com/admin/test1/new'
        self.assertEqual(url, expected)

        url = request.route_url('admin_edit', classname='test1', id=1)
        expected = 'http://example.com/admin/test1/1/edit'
        self.assertEqual(url, expected)


class FunctionalTests(unittest.TestCase):

    permissions = ['sqladmin']

    def get_user_permissions(self, *args, **kw):
        return self.permissions

    def get_user_from_request(self, *args, **kw):
        return None

    def main(self, settings):
        self.session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
        Base = extended_declarative_base(
            self.session,
            metadata=sa.MetaData('sqlite:///:memory:'))

        class Test1(Base):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(50), nullable=False)

        class Test2(Base):
            idtest = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(50), nullable=False)

        Base.metadata.create_all()

        self.Test1 = Test1
        self.Test2 = Test2
        with transaction.manager:
            self.value1 = Test1(name='Bob')
            self.session.add(self.value1)
            self.value2 = Test2(name='Bob')
            self.session.add(self.value2)


        session_factory = UnencryptedCookieSessionFactoryConfig('session_key')
        config = Configurator(settings=settings,
                              session_factory=session_factory,
                              )
        # Authentification
        authentication_policy = AuthTktAuthenticationPolicy(
            'authentication.key',
            callback=self.get_user_permissions,
            debug=True,
            hashalg='sha512',
            )
        authorization_policy = ACLAuthorizationPolicy()
        config.set_authentication_policy(authentication_policy)
        config.set_authorization_policy(authorization_policy)
        config.set_request_property(self.get_user_from_request, 'user', reify=True)

        config.add_static_view('static', 'static', cache_max_age=3600)
        config.include('pyramid_sqladmin')
        config.scan()
        return config.make_wsgi_app()

    def setUp(self):
        clear_mappers()
        pysqla.AVAILABLE_OBJECTS = pysqla._marker
        self.app = self.main({})
        self.app = twc.middleware.TwMiddleware(self.app)
        self.testapp = TestApp(self.app)

    def __remember(self):
        request = testing.DummyRequest(environ={'SERVER_NAME': 'servername'})
        request.registry = self.app.app.registry
        headers = remember(request, 'Bob')
        return {'Cookie': headers[0][1].split(';')[0]}

    def __forget(self):
        request = testing.DummyRequest(environ={'SERVER_NAME': 'servername'})
        request.registry = self.app.registry
        forget(request)

    def test_home(self):
       response = self.testapp.get('/admin', status=403)
       headers = self.__remember()
       response = self.testapp.get('/admin', headers=headers, status=200)
       self.assertTrue('http://localhost/admin/test1' in response.body)
       self.assertTrue('http://localhost/admin/test2' in response.body)

    def test_admin_list(self):
       response = self.testapp.get('/admin/test1', status=403)
       headers = self.__remember()
       response = self.testapp.get('/admin/test1', headers=headers, status=200)
       self.assertTrue('/admin/test1/1/edit' in response.body)

    def test_add_get(self):
       response = self.testapp.get('/admin/test1/new', status=403)
       headers = self.__remember()
       response = self.testapp.get('/admin/test1/new', headers=headers, status=200)
       expected = '''
<!DOCTYPE html>
<html>
<head><link rel="stylesheet" type="text/css" href="/resources/tw2.forms/static/forms.css" media="all" />
  <title>SQLAdmin</title>
  <meta http-equiv="Content-Type" content="text/html;charset=UTF-8"/>
</head>
<body>
  <form enctype="multipart/form-data" method="post">
    <span class="error"></span>
    <table>
    <tr class="odd required" id="name:container">
      <th><label for="name">Name</label></th>
      <td>
        <input name="name" type="text" id="name" value="" />
        <span id="name:error"></span>
      </td>
    </tr>
    <tr class="error"><td colspan="2">
       <span id=":error"></span>
      </td></tr>
    </table>
    <input type="submit" value="Save"/>
  </form>
</body>
</html>
       '''
       tw2test.assert_eq_xml(response.body, expected)

    def test_add_post(self):
        response = self.testapp.post('/admin/test1/new', status=403)
        headers = self.__remember()
        params = {'name': 'Fred'}
        self.assertEqual(self.Test1.query.count(), 1)
        response = self.testapp.post(
            '/admin/test1/new',
            headers=headers,
            params=params,
            status=302)
        self.assertTrue(
            ('Location', 'http://localhost/admin/test1/2/edit')
            in response._headerlist)
        self.assertEqual(self.Test1.query.count(), 2)

    def test_add_bad_post(self):
        response = self.testapp.post('/admin/test1/new', status=403)
        headers = self.__remember()
        self.assertEqual(self.Test1.query.count(), 1)
        response = self.testapp.post(
            '/admin/test1/new',
            headers=headers,
            status=200)
        self.assertEqual(self.Test1.query.count(), 1)
        expected = '''
        <!DOCTYPE html>
<html>
<head><link rel="stylesheet" type="text/css" href="/resources/tw2.forms/static/forms.css" media="all" />
  <title>SQLAdmin</title>
  <meta http-equiv="Content-Type" content="text/html;charset=UTF-8"/>
</head>
<body>
  <form enctype="multipart/form-data" method="post">
    <span class="error"></span>
    <table>
      <tr class="odd required error"  id="name:container">
        <th><label for="name">Name</label></th>
        <td>
          <input name="name" type="text" id="name" value=""/>
          <span id="name:error">Enter a value</span>
        </td>
      </tr>
      <tr class="error"><td colspan="2">
          <span id=":error"></span>
      </td></tr>
    </table>

    <input type="submit" value="Save"/>
  </form>
</body>
</html>'''
        tw2test.assert_eq_xml(response.body, expected)

    def test_edit_get(self):
       response = self.testapp.get('/admin/test1/1/edit', status=403)
       headers = self.__remember()
       response = self.testapp.get('/admin/test1/1/edit', headers=headers, status=200)
       expected = '''
<!DOCTYPE html>
<html>
<head><link rel="stylesheet" type="text/css" href="/resources/tw2.forms/static/forms.css" media="all" />
  <title>SQLAdmin</title>
  <meta http-equiv="Content-Type" content="text/html;charset=UTF-8"/>
</head>
<body>
  <form enctype="multipart/form-data" method="post">
    <span class="error"></span>
    <table>
    <tr class="odd required" id="name:container">
      <th><label for="name">Name</label></th>
      <td>
        <input name="name" type="text" id="name" value="Bob"/>
        <span id="name:error"></span>
      </td>
    </tr>
    <tr class="error"><td colspan="2">
       <span id=":error"></span>
      </td></tr>
    </table>
    <input type="submit" value="Save"/>
  </form>
</body>
</html>
       '''
       tw2test.assert_eq_xml(response.body, expected)

    def test_edit_post(self):
        response = self.testapp.post('/admin/test1/1/edit', status=403)
        headers = self.__remember()
        params = {'name': 'Fred'}
        self.assertEqual(self.Test1.query.count(), 1)
        response = self.testapp.post(
            '/admin/test1/1/edit',
            headers=headers,
            params=params,
            status=302)
        self.assertTrue(
            ('Location', 'http://localhost/admin/test1/1/edit')
            in response._headerlist)
        self.assertEqual(self.Test1.query.count(), 1)
        v = self.Test1.query.one()
        self.assertEqual(v.name, 'Fred')

    def test_edit_bad_post(self):
        response = self.testapp.post('/admin/test1/1/edit', status=403)
        headers = self.__remember()
        self.assertEqual(self.Test1.query.count(), 1)
        response = self.testapp.post(
            '/admin/test1/1/edit',
            headers=headers,
            status=200)
        self.assertEqual(self.Test1.query.count(), 1)
        expected = '''
        <!DOCTYPE html>
<html>
<head><link rel="stylesheet" type="text/css" href="/resources/tw2.forms/static/forms.css" media="all" />
  <title>SQLAdmin</title>
  <meta http-equiv="Content-Type" content="text/html;charset=UTF-8"/>
</head>
<body>
  <form enctype="multipart/form-data" method="post">
    <span class="error"></span>
    <table>
      <tr class="odd required error"  id="name:container">
        <th><label for="name">Name</name></th>
        <td>
          <input name="name" type="text" id="name" value=""/>
          <span id="name:error">Enter a value</span>
        </td>
      </tr>
      <tr class="error"><td colspan="2">
          <span id=":error"></span>
      </td></tr>
    </table>

    <input type="submit" value="Save"/>
  </form>
</body>
</html>'''
        tw2test.assert_eq_xml(response.body, expected)

    def test_tws_edit_link(self):
        self.assertTrue(self.Test1.tws_edit_link)
        self.assertTrue(self.Test2.tws_edit_link)

