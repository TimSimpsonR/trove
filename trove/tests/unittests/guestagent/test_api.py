#    Copyright 2012 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import mock
import testtools
from testtools.matchers import Is
from testtools.matchers import KeysEqual

import trove.common.context as context
from trove.common import exception
from trove.guestagent import api
from trove.guestagent.api import AGENT_LOW_TIMEOUT
from trove.guestagent.api import AGENT_HIGH_TIMEOUT
from trove import rpc
import trove.common.rpc as trove_rpc

REPLICATION_SNAPSHOT = {'master': {'id': '123', 'host': '192.168.0.1',
                                   'port': 3306},
                        'dataset': {},
                        'binlog_position': 'binpos'}

RPC_API_VERSION = '3.0'


def _mock_call_pwd_change(cmd, version=None, users=None):
    if users == 'dummy'and version == '3.0':
        return True
    else:
        raise BaseException("Test Failed")


def _mock_call(cmd, timerout, version=None, username=None, hostname=None,
               database=None, databases=None):
    #To check get_user, list_access, grant_access, revoke_access in cmd.
    if cmd in ('get_user', 'list_access', 'grant_access', 'revoke_access'):
        if version == '3.0':
            return True
    else:
        raise BaseException("Test Failed")


class ApiTest(testtools.TestCase):
    def setUp(self):
        super(ApiTest, self).setUp()
        self.context = context.TroveContext()
        self.guest = api.API(self.context, 0)
        self.guest._cast = _mock_call_pwd_change
        self.guest._call = _mock_call
        self.FAKE_ID = 'instance-id-x23d2d'
        self.api = api.API(self.context, self.FAKE_ID)

    def test_change_passwords(self):
        self.assertIsNone(self.guest.change_passwords("dummy"))

    def test_get_user(self):
        self.assertTrue(self.guest.get_user("dummyname", "dummyhost"))

    def test_list_access(self):
        self.assertTrue(self.guest.list_access("dummyname", "dummyhost"))

    def test_grant_access(self):
        self.assertTrue(self.guest.grant_access("dumname", "dumhost", "dumdb"))

    def test_revoke_access(self):
        self.assertTrue(self.guest.revoke_access("dumname", "dumhost",
                                                 "dumdb"))

    def test_get_routing_key(self):
        self.assertEqual('guestagent.' + self.FAKE_ID,
                         self.api._get_routing_key())

    @mock.patch('trove.guestagent.models.AgentHeartBeat')
    def test_check_for_heartbeat_positive(self, mock_agent):
        self.assertTrue(self.api._check_for_hearbeat())

    @mock.patch('trove.guestagent.models.AgentHeartBeat')
    def test_check_for_heartbeat_exception(self, mock_agent):
        # TODO(juice): maybe it would be ok to extend the test to validate
        # the is_active method on the heartbeat
        mock_agent.find_by.side_effect = exception.ModelNotFoundError("Uh Oh!")
        # execute
        self.assertRaises(exception.GuestTimeout, self.api._check_for_hearbeat)
        # validate
        self.assertEqual(mock_agent.is_active.call_count, 0)

    @mock.patch('trove.guestagent.models.AgentHeartBeat')
    def test_check_for_heartbeat_negative(self, mock_agent):
        # TODO(juice): maybe it would be ok to extend the test to validate
        # the is_active method on the heartbeat
        mock_agent.is_active.return_value = False
        self.assertRaises(exception.GuestTimeout, self.api._check_for_hearbeat)

    def test_delete_queue(self):
        trove_rpc.delete_queue = mock.Mock()
        # execute
        self.api.delete_queue()
        # verify
        trove_rpc.delete_queue.assert_called_with(self.context, mock.ANY)

    def test_create_user(self):
        self.api._cast = mock.Mock()
        self.api.create_user('test_user')
        self.api._cast.assert_called_once_with(
            'create_user', '3.0', users='test_user')

    # TODO(esp):
    # http://www.voidspace.org.uk/python/mock/compare.html#raising-exceptions
    # def test_self.api._cast_exception(self):
    #     self.api._cast = mock.Mock(side_effect=IOError('host down'))
    #     exp_msg = RpcMsgMatcher('create_user', 'users')
    #     # execute
    #     with testtools.ExpectedException(exception.GuestError,
    #                                      '.* host down'):
    #         self.api.create_user('test_user')
    #     # verify
    #     self._verify_self.api._cast(exp_msg, self.api._cast)

    def test_list_users(self):
        exp_resp = ['user1', 'user2', 'user3']
        self.api._call = mock.Mock(return_value=exp_resp)
        act_resp = self.api.list_users()
        self.api._call.assert_called_once_with(
            "list_users", AGENT_LOW_TIMEOUT, '3.0', limit=None, marker=None,
            include_marker=False)
        self.assertEqual(exp_resp, act_resp)

    # TODO(esp):
    # http://www.voidspace.org.uk/python/mock/compare.html#raising-exceptions
    # def test_self.api._call_exception(self):
    #     self.api._call = mock.Mock(side_effect=IOError('host_down'))
    #     exp_msg = RpcMsgMatcher('list_users', 'limit', 'marker',
    #                             'include_marker')
    #     # execute
    #     with testtools.ExpectedException(exception.GuestError,
    #                                      'An error occurred.*'):
    #         self.api.list_users()
    #     # verify
    #     self._verify_self.api._call(exp_msg, self.api._call)

    def test_delete_user(self):
        self.api._cast = mock.Mock()
        self.api.delete_user('test_user')
        self.api._cast.assert_called_once_with(
            "delete_user", '3.0', user='test_user')

    def test_create_database(self):
        self.api._cast = mock.Mock()
        databases = ['db1', 'db2', 'db3']
        self.api.create_database(databases)
        self.api._cast.assert_called_once_with(
            "create_database", '3.0', databases=databases)

    def test_list_databases(self):
        exp_resp = ['db1', 'db2', 'db3']
        self.api._call = mock.Mock(return_value=exp_resp)
        resp = self.api.list_databases(
            limit=1, marker=2, include_marker=False)
        self.api._call.assert_called_once_with(
            "list_databases", AGENT_LOW_TIMEOUT, '3.0', limit=1, marker=2,
            include_marker=False)
        self.assertEqual(exp_resp, resp)

    def test_delete_database(self):
        self.api._cast = mock.Mock()
        self.api.delete_database('test_database_name')
        self.api._cast.assert_called_once_with(
            "delete_database", '3.0', database='test_database_name')

    def test_enable_root(self):
        self.api._call = mock.Mock(return_value=True)
        self.assertThat(self.api.enable_root(), Is(True))
        self.api._call.assert_called_once_with(
            "enable_root", AGENT_HIGH_TIMEOUT, '3.0')

    def test_disable_root(self):
        self.api._call = mock.Mock(return_value=True)
        self.assertThat(self.api.disable_root(), Is(True))
        self.api._call.assert_called_once_with(
            "disable_root", AGENT_LOW_TIMEOUT, '3.0')

    def test_is_root_enabled(self):
        self.api._call = mock.Mock(return_value=False)
        self.assertThat(self.api.is_root_enabled(), Is(False))
        self.api._call.assert_called_once_with(
            "is_root_enabled", AGENT_LOW_TIMEOUT, '3.0')

    def test_get_hwinfo(self):
        self.api._call = mock.Mock(return_value='[blah]')
        self.assertThat(self.api.get_hwinfo(), Is('[blah]'))
        self.api._call.assert_called_once_with(
            "get_hwinfo", AGENT_LOW_TIMEOUT, '3.0')

    def test_get_diagnostics(self):
        self.api._call = mock.Mock(spec=rpc, return_value='[all good]')
        self.assertThat(self.api.get_diagnostics(), Is('[all good]'))
        self.api._call.assert_called_once_with(
            "get_diagnostics", AGENT_LOW_TIMEOUT, '3.0')

    def test_restart(self):
        self.api._call = mock.Mock()
        self.api.restart()
        self.api._call.assert_called_once_with(
            "restart", AGENT_HIGH_TIMEOUT, '3.0')

    def test_start_db_with_conf_changes(self):
        self.api._call = mock.Mock()
        self.api.start_db_with_conf_changes(None)
        self.api._call.assert_called_once_with(
            "start_db_with_conf_changes", AGENT_HIGH_TIMEOUT, '3.0',
            config_contents=None)

    def test_stop_db(self):
        self.api._call = mock.Mock()
        self.api.stop_db(do_not_start_on_reboot=False)
        self.api._call.assert_called_once_with(
            "stop_db", AGENT_HIGH_TIMEOUT, '3.0',
            do_not_start_on_reboot=False)

    def test_get_volume_info(self):
        fake_resp = {'fake': 'resp'}
        self.api._call = mock.Mock(return_value=fake_resp)
        self.assertThat(self.api.get_volume_info(), Is(fake_resp))
        self.api._call.assert_called_once_with(
            "get_filesystem_stats", AGENT_LOW_TIMEOUT, '3.0', fs_path=None)

    def test_update_guest(self):
        self.api._call = mock.Mock()
        self.api.update_guest()
        self.api._call.assert_called_once_with(
            "update_guest", AGENT_HIGH_TIMEOUT, '3.0')

    def test_create_backup(self):
        self.api._cast = mock.Mock()
        self.api.create_backup({'id': '123'})
        self.api._cast.assert_called_once_with(
            "create_backup", '3.0', backup_info={'id': '123'})

    def test_update_overrides(self):
        self.api._cast = mock.Mock()
        self.api.update_overrides('123')
        self.api._cast.assert_called_once_with(
            "update_overrides", '3.0', overrides='123', remove=False)

    def test_apply_overrides(self):
        self.api._cast = mock.Mock()
        self.api.apply_overrides('123')
        self.api._cast.assert_called_once_with(
            "apply_overrides", '3.0', overrides='123')

    def test_get_replication_snapshot(self):
        exp_resp = REPLICATION_SNAPSHOT
        rpc.call = mock.Mock(return_value=exp_resp)
        exp_msg = RpcMsgMatcher('get_replication_snapshot', 'snapshot_info')
        # execute
        self.api.get_replication_snapshot({})
        # verify
        self._verify_rpc_call(exp_msg, rpc.call)

    def test_attach_replication_slave(self):
        rpc.cast = mock.Mock()
        exp_msg = RpcMsgMatcher('attach_replication_slave',
                                'snapshot', 'slave_config')
        # execute
        self.api.attach_replication_slave(REPLICATION_SNAPSHOT)
        # verify
        self._verify_rpc_cast(exp_msg, rpc.cast)

    def test_detach_replica(self):
        rpc.call = mock.Mock()
        exp_msg = RpcMsgMatcher('detach_replica')
        # execute
        self.api.detach_replica()
        # verify
        self._verify_rpc_call(exp_msg, rpc.call)

    def test_demote_replication_master(self):
        rpc.call = mock.Mock()
        exp_msg = RpcMsgMatcher('demote_replication_master')
        # execute
        self.api.demote_replication_master()
        # verify
        self._verify_rpc_call(exp_msg, rpc.call)

    def _verify_rpc_connection_and_cast(self, rpc, mock_conn, exp_msg):
        rpc.create_connection.assert_called_with(new=True)
        mock_conn.create_consumer.assert_called_with(
            self.api._get_routing_key(), None, fanout=False)
        rpc.cast.assert_called_with(mock.ANY, mock.ANY, exp_msg)

    def test_prepare(self):
        mock_conn = mock.Mock()
        rpc.create_connection = mock.Mock(return_value=mock_conn)
        self.api._cast = mock.Mock()
        self.api.prepare('2048', 'package1', 'db1', 'user1', '/dev/vdt',
                         '/mnt/opt', 'bkup-1232', 'cont', '1-2-3-4',
                         'override')

        self.api._cast.assert_called_once_with(
            "prepare", '3.0', packages='package1', databases='db1',
            memory_mb='2048', users='user1', device_path='/dev/vdt',
            mount_point='/mnt/opt', backup_info='bkup-1232',
            config_contents='cont', root_password='1-2-3-4',
            overrides='override', cluster_config={'id': '2-3-4-5'})

    def test_prepare_with_backup(self):
        mock_conn = mock.Mock()
        rpc.create_connection = mock.Mock(return_value=mock_conn)
        self.api._cast = mock.Mock()

        bkup = {'id': 'backup_id_123'}
        self.api.prepare('2048', 'package1', 'db1', 'user1', '/dev/vdt',
                         '/mnt/opt', bkup, 'cont', '1-2-3-4',
                         'overrides', {"id": "2-3-4-5"})

        self.api._cast.assert_called_once_with(
            "prepare", '3.0', packages='package1', databases='db1',
            memory_mb='2048', users='user1', device_path='/dev/vdt',
            mount_point='/mnt/opt', backup_info=bkup,
            config_contents='cont', root_password='1-2-3-4',
            overrides='overrides', cluster_config={'id': '2-3-4-5'})

    def test_upgrade(self):
        instance_version = "v1.0.1"
        strategy = "pip"
        location = "http://swift/trove-guestagent-v1.0.1.tar.gz"

        mock_conn = mock.Mock()
        rpc.create_connection = mock.Mock(return_value=mock_conn)
        rpc.cast = mock.Mock()
        exp_msg = RpcMsgMatcher(
            'upgrade', 'instance_version', 'location', 'metadata')

        # execute
        self.api.upgrade(instance_version, strategy, location)

        # verify
        self._verify_rpc_cast(exp_msg, rpc.cast)

    def test_rpc_cast_with_consumer_exception(self):
        mock_conn = mock.Mock()
        rpc.create_connection = mock.Mock(side_effect=IOError('host down'))
        rpc.cast = mock.Mock()
        # execute
        with testtools.ExpectedException(exception.GuestError, '.* host down'):
            self.api.prepare('2048', 'package1', 'db1', 'user1', '/dev/vdt',
                             '/mnt/opt')
        # verify
        rpc.create_connection.assert_called_with(new=True)
        self.assertThat(mock_conn.call_count, Is(0))
        self.assertThat(rpc.cast.call_count, Is(0))

    def _verify_rpc_call(self, exp_msg, mock_call=None):
        mock_call.assert_called_with(self.context, mock.ANY, exp_msg,
                                     mock.ANY)

    def _verify_rpc_cast(self, exp_msg, mock_cast=None):
        mock_cast.assert_called_with(mock.ANY,
                                     mock.ANY, exp_msg)


class ApiStrategyTest(testtools.TestCase):

    @mock.patch('trove.guestagent.api.API.__init__',
                mock.Mock(return_value=None))
    def test_guest_client(self):
        from trove.common.remote import guest_client
        client = guest_client(mock.Mock(), mock.Mock(), 'mongodb')
        self.assertFalse(hasattr(client, 'add_config_servers2'))
        self.assertTrue(callable(client.add_config_servers))


class RpcMsgMatcher(object):
    def __init__(self, method, *args_dict):
        self.wanted_method = method
        self.wanted_dict = KeysEqual('version', 'method', 'args', 'namespace')
        args_dict = args_dict or [{}]
        self.args_dict = KeysEqual(*args_dict)

    def __eq__(self, arg):
        if self.wanted_method != arg['method']:
            raise Exception("Method does not match: %s != %s" %
                            (self.wanted_method, arg['method']))
            #return False
        if self.wanted_dict.match(arg) or self.args_dict.match(arg['args']):
            raise Exception("Args do not match: %s != %s" %
                            (self.args_dict, arg['args']))
            #return False
        return True

    def __repr__(self):
        return "<Dict: %s>" % self.wanted_dict
