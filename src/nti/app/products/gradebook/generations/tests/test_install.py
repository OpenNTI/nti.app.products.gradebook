#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import has_key
from hamcrest import assert_that

import unittest

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

from nti.dataserver.tests import mock_dataserver


class TestFunctionalInstall(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    @mock_dataserver.WithMockDSTrans
    def test_installed(self):
        conn = mock_dataserver.current_transaction
        root = conn.root()
        generations = root['zope.generations']
        assert_that(generations, has_key('nti.dataserver-products-gradebook'))
