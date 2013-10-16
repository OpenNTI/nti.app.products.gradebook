#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

from nti.dataserver.tests.mock_dataserver import SharedConfiguringTestBase

class ConfiguringTestBase(SharedConfiguringTestBase):
    set_up_packages = ('nti.dataserver', 'nti.app.products.gradebook')
