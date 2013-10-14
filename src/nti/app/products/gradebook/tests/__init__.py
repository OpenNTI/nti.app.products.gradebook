#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import nti.dataserver as dataserver

import nti.app.products.gradebook as gradebook

from nti.dataserver.tests.mock_dataserver import ConfiguringTestBase as DSBaseConfiguringTestBase
from nti.dataserver.tests.mock_dataserver import SharedConfiguringTestBase as DSSharedConfiguringTestBase

class BaseConfiguringTestBase(DSBaseConfiguringTestBase):
    set_up_packages = (dataserver, gradebook)

class SharedConfiguringTestBase(DSSharedConfiguringTestBase):
    set_up_packages = (dataserver, gradebook)

ConfiguringTestBase = SharedConfiguringTestBase  # BWC
