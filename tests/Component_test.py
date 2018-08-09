import pytest
import io
import queue
import time
import serial

from tests import example

@pytest.fixture
def newpreamp(request):
    stream = serial.serial_for_url('loop://', timeout=1)
    preamp = example.preampComponent(name = 'pyIOT_test_preamp', stream = stream)

    def exitpreamp():
        preamp.exit()

    request.addfinalizer(exitpreamp)
    return preamp

def receiveFromComponent(component, cmd):
    eq = queue.Queue()
    component._stream.write(cmd)
    component._start(eq)
    return eq

def receiveFromIoT(component, p, v):
    eq = queue.Queue()
    component._start(eq)
    component.updateComponent(p,v)
    time.sleep(0.5)
    return component._stream.readline()

def test_preamp_power_on(newpreamp):
    q = receiveFromComponent(newpreamp, b'P1P1\n')

    msg = q.get(timeout=2)
    print (msg)

    assert(msg['property']=='powerState')
    assert(msg['value']=='ON')

def test_preamp_power_off(newpreamp):
    q = receiveFromComponent(newpreamp, b'P1P0\n')

    msg = q.get(timeout=2)
    print (msg)

    assert(msg['property']=='powerState')
    assert(msg['value']=='OFF')

def test_preamp_volume(newpreamp):
    q = receiveFromComponent(newpreamp, b'P1VM+8.5\n')

    msg = q.get(timeout=2)
    print (msg)

    assert(msg['property']=='volume')
    assert(msg['value']==83)

def test_preamp_power_off_iot(newpreamp):
    val = receiveFromIoT(newpreamp, 'powerState', 'OFF')
    assert(val==b'P1P0')

def test_preamp_query(newpreamp):
    q = receiveFromComponent(newpreamp, b'P1P1')
    time.sleep(5)
    assert(newpreamp._stream.getvalue()==b'P1P1P1?\n')

def test_preamp_query_off(newpreamp):
    q = receiveFromComponent(newpreamp, b'P1P0')
    time.sleep(5)
    assert(newpreamp._stream.getvalue()==b'P1P0P1P?\n')
