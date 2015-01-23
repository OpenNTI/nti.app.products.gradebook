#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division

__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import fudge

from unittest import TestCase

from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains

from nti.app.products.gradebook.views import GradeBookSummaryView

from nti.app.testing.request_response import DummyRequest

from nti.externalization.representation import WithRepr

@WithRepr
class MockGrade( object ):

	def __init__( self, value='0' ):
		self.value = value

@WithRepr
class MockSummary( object ):
	"By default, every field is non-null at the start of ascending order."

	def __init__( self, alias='a', last_name='a', username='a',
					overdue_count=0, upgraded_count=0, final_grade=MockGrade() ):
		self.alias = alias
		self.last_name = last_name
		self.username = username
		self.overdue_count = overdue_count
		self.upgraded_count = upgraded_count
		self.final_grade = final_grade

class TestGradeBookSummary( TestCase ):

	@fudge.patch( 'pyramid.url.URLMethodsMixin.current_route_path' )
	def test_sorting( self, mock_url ):
		"Test sorting/batching params of gradebook summary."
		mock_url.is_callable().returns( '/path/' )
		request = DummyRequest( params={} )
		view = GradeBookSummaryView( request )
		do_sort = view._get_user_result_set

		# Empty
		result = do_sort( {}, () )
		assert_that( result, has_length( 0 ))

		# Single sort by final
		summary = MockSummary()
		summaries = ( summary, )
		request.params={ 'sortOn' : 'FINALGRADE' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 1 ))

		# Single sort by alias
		summaries = ( summary, )
		request.params={ 'sortOn' : 'aliaS' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 1 ))
		assert_that( result, contains( summary ))

		# Single sort by something else, which defaults to last_name
		summaries = ( summary, )
		request.params={ 'sortOn' : 'XXX', 'sortOrder': 'ascending' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 1 ))
		assert_that( result, contains( summary ))

		# Case insensitive sort by final
		summary2 = MockSummary()
		summary2.final_grade = MockGrade( '10' )
		summary3 = MockSummary()
		summary3.final_grade = MockGrade( '90' )
		summary4 = MockSummary()
		summary4.final_grade = None

		summaries = [ summary4, summary3, summary2, summary ]
		request.params={ 'sortOn' : 'finalgradE', 'sortOrder': 'ascending' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 4 ))
		assert_that( result, contains( summary4, summary, summary2, summary3 ))

		# Alias; desc
		summary2.alias = 'zzzz'
		summary3.alias = 'mmm'
		summary4.alias = None
		request.params={ 'sortOn' : 'ALIAS', 'sortOrder': 'descending' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 4 ))
		assert_that( result, contains( summary2, summary3, summary, summary4 ))

		# Default; desc
		summary2.last_name = 'zzzz'
		summary3.last_name = 'mmm'
		summary4.last_name = None
		request.params={ 'sortOn' : 'XXX', 'sortOrder': 'descending' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 4 ))
		assert_that( result, contains( summary2, summary3, summary, summary4 ))

		# Username; ascending
		summary2.username = 'zzzz'
		summary3.username = 'mmm'
		summary4.username = None
		request.params={ 'sortOn' : 'username' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 4 ))
		assert_that( result, contains( summary4, summary, summary3, summary2 ))

		# Same with batch
		request.params={ 'sortOn' : 'username', 'batchSize' : 1, 'batchStart' : 0 }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 1 ))
		assert_that( result, contains( summary4 ))

