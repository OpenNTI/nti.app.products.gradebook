#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division

__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import fudge

from unittest import TestCase

from hamcrest import is_
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains
from hamcrest import contains_inanyorder

from nti.app.products.gradebook.views import GradeBookSummaryView
from nti.app.products.gradebook.gradebook import GradeBook

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
					overdue_count=0, ungraded_count=0, final_grade=MockGrade() ):
		self.alias = alias
		self.last_name = last_name
		self.username = username
		self.overdue_count = overdue_count
		self.ungraded_count = ungraded_count
		self.final_grade = final_grade

class TestGradeBookSummary( TestCase ):

	@fudge.patch( 'pyramid.url.URLMethodsMixin.current_route_path' )
	@fudge.patch( 'nti.app.products.gradebook.views.GradeBookSummaryView._get_final_grade_entry' )
	@fudge.patch( 'nti.app.products.gradebook.views.GradeBookSummaryView._get_assignment_for_course' )
	def test_sorting( self, mock_url, mock_final_grade, mock_assignments ):
		"Test sorting/batching params of gradebook summary."
		mock_url.is_callable().returns( '/path/' )
		mock_final_grade.is_callable()
		mock_assignments.is_callable()
		request = DummyRequest( params={} )
		view = GradeBookSummaryView( GradeBook(), request )
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
		request.params={ 'sortOn' : 'aliaS' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 1 ))
		assert_that( result, contains( summary ))

		# Single sort by something else, which defaults to last_name
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

	@fudge.patch( 'nti.app.products.gradebook.views.GradeBookSummaryView._get_students' )
	@fudge.patch( 'nti.app.products.gradebook.views.GradeBookSummaryView._get_final_grade_entry' )
	@fudge.patch( 'nti.app.products.gradebook.views.GradeBookSummaryView._get_assignment_for_course' )
	def test_filtering( self, mock_get_students, mock_final_grade, mock_assignments ):
		"Test sorting/batching params of gradebook summary."
		mock_final_grade.is_callable()
		mock_assignments.is_callable()
		request = DummyRequest( params={} )
		view = GradeBookSummaryView( GradeBook(), request )
		do_filter = view._do_get_user_summaries

		# Empty
		mock_get_students.is_callable().returns( ( (),0 ) )
		result, count = do_filter()
		assert_that( result, has_length( 0 ))
		assert_that( count, is_( 0 ))

		# Single with no filter
		summary = MockSummary()
		summaries = ( summary, )
		mock_get_students.is_callable().returns( ( summaries, 50 ) )
		result, count = do_filter()
		assert_that( list( result ), has_length( 1 ))
		assert_that( count, is_( 50 ))

		# Single filter ungraded
		request.params={ 'filter' : 'UnGRADED' }
		result, count = do_filter()
		assert_that( list( result ), has_length( 0 ))

		# Single filter overdue
		request.params={ 'filter' : 'overDUE' }
		result, count = do_filter()
		assert_that( list( result ), has_length( 0 ))

		# actionable
		request.params={ 'filter' : 'actionablE' }
		result, count = do_filter()
		assert_that( list( result ), has_length( 0 ))

		# Multiple filters
		request.params={ 'filter' : 'actionablE,open' }
		result, count = do_filter()
		assert_that( list( result ), has_length( 0 ))

		# Multiple summaries/ filter ungraded
		summary2 = MockSummary()
		summary2.ungraded_count = 9
		summary3 = MockSummary()
		summary3.ungraded_count = 10
		summary4 = MockSummary()
		summary4.ungraded_count = 99

		summaries = [ summary4, summary3, summary2, summary ]
		mock_get_students.is_callable().returns( ( summaries, 50 ) )

		request.params={ 'filter' : 'ungraded,open' }
		result, count = do_filter()
		result = list( result )
		assert_that( result, has_length( 3 ))
		assert_that( result, contains_inanyorder( summary2, summary3, summary4 ))
		assert_that( count, is_( 50 ))

		# Filter overdue
		summary2.overdue_count = 9
		summary3.overdue_count = 10
		summary4.overdue_count = 99
		request.params={ 'filter' : 'OVerDUE,open' }

		result, count = do_filter()
		result = list( result )
		assert_that( result, has_length( 3 ))
		assert_that( result, contains_inanyorder( summary2, summary3, summary4 ))
		assert_that( count, is_( 50 ))

		# Actionable
		summary4.overdue_count = 0
		summary4.ungraded_count = 0
		request.params={ 'filter' : 'ACTIONAble,open' }

		result, count = do_filter()
		result = list( result )
		assert_that( result, has_length( 2 ))
		assert_that( result, contains_inanyorder( summary2, summary3 ))
		assert_that( count, is_( 50 ))
