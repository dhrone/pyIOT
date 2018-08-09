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
