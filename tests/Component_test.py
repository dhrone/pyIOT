import pytest
import queue
import time

from tests import example
from tests import simulator

@pytest.fixture
def newpreamp(request):
    stream = simulator.preampSim()
    preamp = example.preampComponent(name = 'pyIOT_test_preamp', stream = stream)

    def exitpreamp():
        preamp.exit()

    request.addfinalizer(exitpreamp)
    return preamp

def test_preamp_power_on(newpreamp):
    q = queue.Queue()
    newpreamp._start(q)
    newpreamp._stream.write(b'P1P1\n')

    msg = q.get(timeout=2)
    print (msg)

    assert(msg['property']=='powerState')
    assert(msg['value']=='ON')

def test_preamp_query_startup(newpreamp):
    q = queue.Queue()

    assert(newpreamp.properties['powerState'] == None)
    assert(newpreamp.properties['input'] == None)
    assert(newpreamp.properties['volume'] == None)
    assert(newpreamp.properties['muted'] == None)

    newpreamp._start(q)
    time.sleep(8)

    assert(newpreamp.properties['powerState'] == 'OFF')

def test_preamp_query_running(newpreamp):
    q = queue.Queue()
    newpreamp._start(q)
    newpreamp._stream.frontPanel('power', True)
    time.sleep(1)

    assert(newpreamp.properties['powerState'] == 'ON')
    time.sleep(8)

    assert(newpreamp.properties['powerState'] == 'ON')
    assert(newpreamp.properties['input'] == 'CD')
    assert(newpreamp.properties['volume'] == 60)
    assert(newpreamp.properties['muted'] == False)

def test_updateComponent(newpreamp):
    q = queue.Queue()
    newpreamp._start(q)
    newpreamp._stream.frontPanel('power', True)
    time.sleep(1)

    newpreamp.updateComponent('input','TV')
    time.sleep(6)

    assert(newpreamp.properties['input']=='TV')

def test_updateThing(newpreamp):
    q = queue.Queue()
    newpreamp._start(q)

    msg = q.get(timeout=8)
    assert(msg['property']=='powerState')
    assert(msg['value']=='OFF')

    newpreamp._stream.frontPanel('power', True)

    msg = q.get(timeout=8)
    assert(msg['property']=='powerState')
    assert(msg['value']=='ON')
