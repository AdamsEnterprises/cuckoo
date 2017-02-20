# Copyright (C) 2016-2017 Cuckoo Foundation.
# This file is part of Cuckoo Sandbox - http://www.cuckoosandbox.org
# See the file 'docs/LICENSE' for copying permission.

import mock
import os
import pytest
import shutil
import tempfile

import cuckoo

from cuckoo.common.config import config
from cuckoo.common.files import Folders, Files
from cuckoo.common.utils import Singleton
from cuckoo.core.init import write_supervisor_conf, write_cuckoo_conf
from cuckoo.core.resultserver import ResultServer
from cuckoo.main import main, cuckoo_create
from cuckoo.misc import set_cwd, cwd

class TestInit(object):
    def setup(self):
        set_cwd(tempfile.mkdtemp())

    def test_exists(self):
        filepath = cwd("supervisord.conf")
        open(filepath, "wb").write("foo")

        write_supervisor_conf(None)
        assert open(filepath, "rb").read() == "foo"

    def test_new(self):
        venv = os.environ.pop("VIRTUAL_ENV", None)

        write_supervisor_conf(None)
        buf = open(cwd("supervisord.conf"), "rb").read()

        assert "command = cuckoo -d -m 10000" in buf

        if venv:
            os.environ["VIRTUAL_ENV"] = venv

    @pytest.mark.skipif("sys.platform != 'linux2'")
    def test_venv_new(self):
        venv = os.environ.pop("VIRTUAL_ENV", None)
        os.environ["VIRTUAL_ENV"] = cwd()

        write_supervisor_conf(None)
        buf = open(cwd("supervisord.conf"), "rb").read()

        cuckoo_path = "%s/bin/cuckoo" % cwd()
        assert "command = %s -d -m 10000" % cuckoo_path in buf

        os.environ["VIRTUAL_ENV"] = venv

    def test_cuckoo_init(self):
        """Tests that 'cuckoo init' works with a new CWD."""
        with pytest.raises(SystemExit):
            main.main(
                ("--cwd", cwd(), "--nolog", "init"),
                standalone_mode=False
            )

        assert os.path.exists(os.path.join(cwd(), "mitm.py"))
        assert os.path.exists(os.path.join(cwd(), "conf"))
        assert os.path.exists(os.path.join(cwd(), "storage"))
        assert os.path.exists(os.path.join(cwd(), "storage", "binaries"))
        assert os.path.exists(os.path.join(cwd(), "storage", "analyses"))
        assert os.path.exists(os.path.join(cwd(), "storage", "baseline"))
        assert os.path.exists(os.path.join(cwd(), "log"))

    def test_cuckoo_init_main(self):
        """Tests that 'cuckoo' works with a new CWD."""
        main.main(
            ("--cwd", cwd(), "--nolog"),
            standalone_mode=False
        )
        assert os.path.exists(os.path.join(cwd(), "mitm.py"))

    @mock.patch("cuckoo.main.load_signatures")
    def test_cuckoo_init_main_nosigs(self, p):
        """Ensure load_signatures() isn't called for 'cuckoo' with new CWD."""
        main.main(
            ("--cwd", cwd(), "--nolog"),
            standalone_mode=False
        )
        assert os.path.exists(os.path.join(cwd(), "mitm.py"))
        p.assert_not_called()

    def test_cuckoo_init_no_resultserver(self):
        """Tests that 'cuckoo init' doesn't launch the ResultServer."""
        with pytest.raises(SystemExit):
            main.main(
                ("--cwd", cwd(), "--nolog", "init"),
                standalone_mode=False
            )

        # We copy the monitor binary directory over from user-CWD (which is
        # also present in the Travis CI environment, etc) as otherwise the
        # following call will raise an exception about not having found the
        # monitoring binaries.
        shutil.rmtree(os.path.join(cwd(), "monitor"))
        shutil.copytree(
            os.path.expanduser("~/.cuckoo/monitor"),
            os.path.join(cwd(), "monitor")
        )

        # Raises CuckooCriticalError if ResultServer can't bind (which no
        # longer happens now, naturally).
        main.main(
            ("--cwd", cwd(), "--nolog", "init"),
            standalone_mode=False
        )

        assert ResultServer not in Singleton._instances

    def test_cuckoo_conf(self):
        Folders.create(cwd(), "conf")
        write_cuckoo_conf()

    def test_cuckoo_create(self):
        # Specifically try to create $CWD/signatures/__init__.pyc to ensure
        # that our .pyc filtering works.
        initpyc = os.path.join(
            cuckoo.__path__[0], "data", "signatures", "__init__.pyc"
        )
        open(initpyc, "wb").close()

        cuckoo_create("derpy")
        assert os.path.exists(cwd(".cwd"))
        assert os.path.exists(cwd("conf", "esx.conf"))
        assert os.path.exists(cwd("analyzer", "windows", "analyzer.py"))
        assert os.path.exists(cwd("monitor", "latest"))
        assert os.path.exists(cwd("distributed", "settings.py"))
        assert not os.path.exists(cwd("signatures", "__init__.pyc"))
        assert os.path.exists(initpyc)
        os.unlink(initpyc)

    def test_cuckoo_create2(self):
        cuckoo_create(cfg={
            "auxiliary": {
                "sniffer": {
                    "tcpdump": "dumping.elf",
                },
            },
        })
        buf = open(cwd("conf", "auxiliary.conf"), "rb").read()
        assert "tcpdump = dumping.elf" in buf

    def test_cuckoo_init_kv_conf(self):
        filepath = Files.temp_put(
            "cuckoo.cuckoo.version_check = no"
        )

        with pytest.raises(SystemExit):
            main.main(
                ("--cwd", cwd(), "init", "--conf", filepath),
                standalone_mode=False
            )

        assert config("cuckoo:cuckoo:version_check") is False