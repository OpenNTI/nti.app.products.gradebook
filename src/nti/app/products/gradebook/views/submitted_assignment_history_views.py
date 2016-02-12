#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time
import operator

from six import string_types

from zope import component

from pyramid.view import view_config
from pyramid import httpexceptions as hexc

from natsort import natsort_key

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.app.products.gradebook import MessageFactory as _

from nti.app.products.gradebook.interfaces import ACT_VIEW_GRADES

from nti.app.products.gradebook.interfaces import IGradeBookEntry
from nti.app.products.gradebook.interfaces import ISubmittedAssignmentHistoryBase

from nti.app.products.gradebook.utils import replace_username

from nti.appserver.interfaces import IIntIdUserSearchPolicy

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE
from nti.contenttypes.courses.interfaces import ES_CREDIT_NONDEGREE

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import Entity
from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.externalization.externalization import StandardExternalFields

from nti.externalization.interfaces import LocatedExternalDict

from nti.externalization.oids import to_external_ntiid_oid

ITEMS = StandardExternalFields.ITEMS

# Due to heavy use of interfaces, disable warning about
# "too many positional arguments" (because of self),
# and the warning about disabling the warning
# pylint:disable=E1121,I0011

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=ISubmittedAssignmentHistoryBase,
			 permission=nauth.ACT_READ)
class SubmittedAssignmentHistoryGetView(AbstractAuthenticatedView,
										BatchingUtilsMixin):
	"""
	Support retrieving the submitted assignment history (and summaries)
	typically for a particular column of the gradebok.

	The return dictionary will have the following entries:

	Items
		A dictionary from student username to submission history item.
		If you sort, this will be a list of (username, submission)
		pairs, where the submission may be null.

	FilteredTotalItemCount
		The total number of items that match the filter, if specified;
		identical to TotalItemCount if there is no filter.

	TotalItemCount
		How many total submissions there are. If any filter, sorting
		or paging options are specified, this will be the same as the
		number of enrolled students in the class (because we will
		ultimately return that many rows due to the presence of null
		rows for non-submitted students).

	TotalNonNullItemCount
		How many total submissions there are. This does not depend
		on the presence of any filter, sort, or paging options.

	FilteredTotalNonNullItemCount
		How many submissions match the filter.

	The following query parameters are supported:

	sortOn
		The field to sort on. Options are ``realname`` to sort on the parts
		of the user's realname ("lastname" first; note that this is
		imprecise and likely to sort non-English names incorrectly.);
		``dateSubmitted``; ``feedbackCount``; ``gradeValue``; ``username``.
		Note that if you sort, the Items dictionary becomes an ordered
		list of pairs. Also note that sorting by gradeValue may not have
		the expected results, depending on what sort of grade values are
		being used; we do our best.

	sortOrder
		The sort direction. Options are ``ascending`` and
		``descending``. If you do not specify, a value that makes the
		most sense for the ``sortOn`` parameter will be used by
		default.

	filter
		Whether to filter the returned data in some fashion. Several
		values are defined:

		* ``LegacyEnrollmentStatusForCredit``: Only students that are
		  enrolled for credit are returned. An entry in the dictionary is
		  returned for each such student, even if they haven't submitted;
		  the value for students that haven't submitted is null.

		* ``LegacyEnrollmentStatusOpen``: Only students that are
		  enrolled NOT for credit are returned. An entry in the dictionary is
		  returned for each such student, even if they haven't submitted;
		  the value for students that haven't submitted is null.

		* ``HasSubmission``: Only students that have a submission are returned.
		  Can be combined with the enrollment status filter using a comma.

		* ``NoSubmission``: Only students that do not have a submission are returned.
		  Can be combined with the enrollment status filter using a comma.

	batchSize
		Integer giving the page size. Must be greater than zero.
		Paging only happens when this is supplied together with
		``batchStart`` (or ``batchAround`` for those views that support it).

	batchStart
		Integer giving the index of the first object to return,
		starting with zero. Paging only happens when this is
		supplied together with ``batchSize``.

	batchAround
		String parameter giving the ``OID`` of an object to build a
		batch (page) around. When you give this parameter,
		``batchStart`` is ignored and the found object is centered at
		one-half the ``batchSize`` in the returned page---assuming
		there are enough following objects). If there are very few
		matching objects, and/or the ``batchSize`` is small, then the
		object may not be centered, but we do guarantee it will be in
		the returned values. If the object is not found (after all the
		filters are applied) then an empty batch is returned. (Even if
		you supply this value, you should still supply a value for
		``batchStart`` such as 1).

	batchAroundCreator
		String parameter giving the ``Creator`` of an object to build a batch (page)
		around. Otherwise identical to ``batchAround``.

	usernameSearchTerm
		If provided, only users that match this search term
		will be returned. This search is based on the username and
		realname and alias, and does prefix matching, the same as
		the normal search algorithm for users. This is independent
		of filtering.
	"""

	_BATCH_LINK_DROP_PARAMS = BatchingUtilsMixin._BATCH_LINK_DROP_PARAMS + ('batchAroundCreator',)

	def __init__(self, request):
		super(SubmittedAssignmentHistoryGetView,self).__init__(request)
		self.context = request.context
		self.grade_column = IGradeBookEntry(self.context)

	def _make_force_placeholder_usernames(self, sorted_usernames, sorted_reverse):
		"""
		Given the sorted usernames as a list, see if we can pick out the usernames
		that belong to the requested batch page, and if so, filter out
		data-loading for everybody else.
		"""
		batch_size, batch_start = self._get_batch_size_start()
		if batch_size is None or batch_start is None:
			return ()

		if self.request.params.get('batchAroundCreator'):
			# The want us to compute a starting index. We can do this, since
			# 'creator' is the same as the username for all cases
			batch_around = self.request.params['batchAroundCreator'].lower()
			test = lambda x: x.lower() == batch_around

			# While this returns a value, we're interested in its side effect
			# of changing the batch_start for us
			self._batch_on_item(sorted_usernames, test)
			batch_size, batch_start = self._get_batch_size_start()

			# Since we've done this already, we can
			# clear the parameter so we don't try to do it again.
			del self.request.GET['batchAroundCreator']

		for x in self._BATCH_LINK_DROP_PARAMS:
			if self.request.params.get(x):
				return ()

		forced_placeholder_usernames = None
		end_idx = batch_start + batch_size

		if batch_start >= len(sorted_usernames):
			# ignore everyone!
			forced_placeholder_usernames = set(sorted_usernames)
		elif batch_start > 0:
			# Before the batch
			forced_placeholder_usernames = sorted_usernames[0:batch_start - 1]
			# after the batch. Note that this is fine even if end_idx is greater than len
			forced_placeholder_usernames.extend( sorted_usernames[end_idx:] )
			forced_placeholder_usernames = set(forced_placeholder_usernames )
		else: # batch_start == 0
			# after the batch
			forced_placeholder_usernames = set( sorted_usernames[end_idx:] )

		return forced_placeholder_usernames

	def _do_sort_realname(self, filter_usernames, sort_reverse):
		# An alternative way to do this would be to get the
		# intids of the users (available from the EntityContainer)
		# and then have an index on the reverse name in the entity
		# catalog (we have the name parts, but keyword indexes are
		# not sortable)
		def _key(username):
			user = Entity.get_entity(username)
			if user is None: # deleted
				return username
			parts = IFriendlyNamed(user).get_searchable_realname_parts()
			if not parts:
				return username

			parts = reversed(parts) # last name first
			return ' '.join(parts).lower()

		filter_usernames = sorted(filter_usernames,
								  key=_key,
								  reverse=sort_reverse)

		place_holder = self._make_force_placeholder_usernames(filter_usernames, sort_reverse)
		items_iter = self.context.items(usernames=filter_usernames,
										placeholder=None,
										forced_placeholder_usernames=place_holder)
		return items_iter

	def __sort_usernames_by_submission(self, filter_usernames, sort_reverse=False, key=None):
		"""
		Divides the users into two parts, those that have a submission and those that don't.
		Based on the key you provide, usernames that have a grade entry (username, IGrade)
		will be sorted by that, only for those that have a submission. All other users
		will be by username at the end.

		Return
		"""
		sorted_usernames = sorted(filter_usernames, reverse=sort_reverse)

		# Iterate the grade column in the order of sorted usernames so that
		# the stable sort will preserve username sort order for ties
		# (if we just use column.items(), we always get ascending)
		grade_column = self.grade_column
		in_gradebook = [k for k in sorted_usernames if k in grade_column ]

		sorted_items_by_grade_attribute = sorted( ( (k, grade_column[k]) for k in in_gradebook),
													key=key,
													reverse=sort_reverse )

		sorted_usernames_by_grade_attribute = map(operator.itemgetter(0),
												  sorted_items_by_grade_attribute)
		# Now everyone that has no grade is always at the end, sorted by username.
		# We can return placeholders for everyone who has no submission by definition
		# because of the one-to-one correspondence
		# NOTE: If we do this, we get different return value than when sorting by username (missing grades)
		# Users who have dropped the course or something?
		users_with_grades = set(sorted_usernames_by_grade_attribute)
		users_without_grades = {x for x in filter_usernames if x not in users_with_grades}
		assert users_with_grades.isdisjoint(users_without_grades)

		for u in sorted_usernames:
			if u not in users_with_grades:
				sorted_usernames_by_grade_attribute.append(u)

		assert len(sorted_usernames_by_grade_attribute) == len(sorted_usernames)
		return sorted_usernames_by_grade_attribute, users_with_grades, users_without_grades

	def _do_sort_feedbackCount(self, filter_usernames, sort_reverse):
		x = self.__sort_usernames_by_submission(filter_usernames,
												sort_reverse,
												key=None)
		filter_usernames, _, users_without_grades = x
		# By forcing placeholders on those we know haven't submitted
		# (because they have no grade) we can be a little bit faster.
		# Unfortunately, we cannot apply the standard batch-based trick
		# because we don't have sorted usernames yet; also, it would
		# break the sort.
		all_items = self.context.items(usernames=filter_usernames,
									   placeholder=None,
									   forced_placeholder_usernames=users_without_grades)
		# Choose a value to use for placeholders that always places them
		# at the end of the list no matter which direction
		if sort_reverse:
			missing_value = -1 # impossible small
		else:
			missing_value = 10000 # improbably large

		key = lambda x: x[1].FeedbackCount if x[1] else missing_value

		# Using batches and heapq.nlargest/smallest has only a very tiny
		# performance edge, if any, over simply sorting everything, as we're
		# dominated by data access time. It's not worth the complexity.
		items_iter = sorted(all_items,
							key=key,
							reverse=sort_reverse)
		return items_iter

	def __do_sort_by_grade_attribute(self, filter_usernames, sort_reverse, key):
		"""
		Sorts directly using the grade values contained in the
		gradebook. User names that do not have a grade are *always*
		sorted to the end, regardless of the sort direction
		"""

		x = self.__sort_usernames_by_submission(filter_usernames,
												sort_reverse,
												key)
		filter_usernames, _, users_without_grades = x

		# Now everyone that has no grade is always at the end, sorted by username.
		# We can return placeholders for everyone who has no submission by definition
		# because of the one-to-one correspondence
		# NOTE: If we do this, we get different return value than when sorting by username (missing grades)
		# Users who have dropped the course or something?
		force_ignore_placeholders = users_without_grades

		# Now if we're able to do batch-based placeholders, add those
		# too
		force_ignore_placeholders.update(self._make_force_placeholder_usernames(filter_usernames,
																				sort_reverse))

		items_iter = self.context.items(usernames=filter_usernames,
										placeholder=None,
										forced_placeholder_usernames=force_ignore_placeholders)
		return items_iter

	def _do_sort_dateSubmitted(self, filter_usernames, sort_reverse):
		# XXX: This used to be true, but now we allow deleting individual grades:

		# We can optimize this by sorting on the created dates of the grade
		# in the gradebook; those should correspond one-to-one to submitted
		# assignments---we assume as much when we set TotalNonNullItemCount.
		# (The exception will be if an instructor manually assigns a grade *before*
		# the submission occurs. However, the cases where that currently happens
		# we aren't expecting a submission at all, plus that case causes the creation
		# of a fake submission anyway).
		# This will let us apply the force-placeholder trick
		# return self.__do_sort_by_grade_attribute( filter_usernames,
		#										   sort_reverse,
		#										   key=lambda x: x[1].createdTime)

		# So now this is almost exactly like sorting by feedback count
		x = self.__sort_usernames_by_submission(filter_usernames,
												sort_reverse,
												key=None)
		filter_usernames, _, _users_without_grades = x
		all_items = self.context.items(usernames=filter_usernames,
									   placeholder=None)

		if sort_reverse:
			missing_value = -1 # impossible small
		else:
			missing_value = time.time() + 10000 # improbably large

		key = lambda x: x[1].createdTime if x[1] else missing_value

		items_iter = sorted(all_items,
							key=key,
							reverse=sort_reverse)
		return items_iter

	def _do_sort_gradeValue(self, filter_usernames, sort_reverse):
		def grade_key(item):
			# Users who have no value for their grade, typically
			# a blank string from the UI, we want to sort to the end
			# as a group.
			# TODO: Not sure how this interacts with the placeholders for
			# people entirely missing a value
			grade = item[1]
			value = grade.value
			if value is None:
				value = 'ZZZZZZZZZZZ'
			if isinstance(value, string_types) and not value.strip():
				value = 'ZZZZZZZZZZZ'
			return natsort_key(value)

		return self.__do_sort_by_grade_attribute( filter_usernames,
												  sort_reverse,
												  key=grade_key )

	def _do_sort_username(self, filter_usernames, sort_reverse, placeholder=True):

		def _key(username):
			result = replace_username(username)
			return result

		filter_usernames = sorted(filter_usernames,
								  key=_key,
								  reverse=sort_reverse)
		kwargs = {}
		if placeholder:
			holder = self._make_force_placeholder_usernames(filter_usernames, sort_reverse)
			kwargs['placeholder'] = None
			kwargs['forced_placeholder_usernames'] = holder

		items_iter = self.context.items(usernames=filter_usernames, **kwargs)
		return items_iter

	def __call__(self):
		request = self.request
		context = self.context
		course = ICourseInstance(context)
		grade_column = self.grade_column

		if not has_permission(ACT_VIEW_GRADES, course, request):
			raise hexc.HTTPForbidden()

		result = LocatedExternalDict()
		column = context.__parent__
		result.__parent__ = column
		result.__name__ = context.__name__

		filter_names = self.request.params.get('filter','').split(',')
		sort_name = self.request.params.get('sortOn')
		username_search_term = self.request.params.get('usernameSearchTerm')
		sort_reverse = self.request.params.get('sortOrder', 'ascending') == 'descending'

		items_iter = None
		items_factory = dict # don't use an ordered dict if we don't sort

		# Get the set of usernames. Right now, we have a direct
		# dependency on the legacy course instance, so we need some better
		# abstractions around this. This will break when we have
		# non-legacy courses.

		# Note that we have to be careful about casing.
		# The grade_column is case-insensitive and so is the usernames= param
		# to our context, but we do several set checks ourself.
		# Always lower-case the username

		# Because the items() method returns things in the order that they are
		# listed in usernames, we can sort usernames first to get the correct
		# order. This is especially helpful when paging as we can consume the part
		# of the generator needed.
		enrollments = ICourseEnrollments(course)
		everyone_usernames = {x.Principal.username.lower()
							  for x in enrollments.iter_enrollments()
							  if x.Principal is not None}
		student_usernames = everyone_usernames - {x.id.lower() for x in course.instructors}
		filter_usernames = student_usernames
		filtered = False
		if filter_names:
			if 	'LegacyEnrollmentStatusForCredit' in filter_names or \
				'LegacyEnrollmentStatusOpen' in filter_names:
				filtered = True

				restricted_usernames = ({x.Principal.username.lower()
										 for x in enrollments.iter_enrollments()
										 # XXX: TODO: Hardcoding the scopes and relationships
										 if x.Scope in (ES_CREDIT_NONDEGREE,
														ES_CREDIT_DEGREE,
														ES_CREDIT)})

				# instructors are also a member of the restricted set,
				# so take them out (otherwise the count will be wrong)
				# (shouldn't be needed to do that on new courses, but necessary
				# for legacy courses)
				if 'LegacyEnrollmentStatusForCredit' in filter_names:
					instructors_ids = {x.id.lower() for x in course.instructors}
					filter_usernames = restricted_usernames - instructors_ids
				elif 'LegacyEnrollmentStatusOpen' in filter_names:
					filter_usernames = student_usernames - restricted_usernames

			if 'HasSubmission' in filter_names or 'NoSubmission' in filter_names:
				filtered = True
				x = self.__sort_usernames_by_submission(filter_usernames)
				_, users_with_grades, users_without_grades = x

				if 'HasSubmission' in filter_names:
					filter_usernames = users_with_grades
				elif 'NoSubmission' in filter_names:
					filter_usernames = users_without_grades

			# XXX: This is a lie unless we also sort (which for all practical use
			# cases, we do) because it depends on placeholders for missing items
			result['TotalItemCount'] = ICourseEnrollments(course).count_enrollments()
			result['FilteredTotalItemCount'] = len(filter_usernames)

		else:
			# No placeholder unless they sort, which means only submitted items.
			# But if they sort, we set items_factory to list, and go through
			# _batch_tuple_iterables which resets these values

			result['TotalItemCount'] = len(context)
			result['FilteredTotalItemCount'] = result['TotalItemCount']
			items_iter = context.items()

		if username_search_term:
			policy = component.getAdapter(self.remoteUser, IIntIdUserSearchPolicy, name='comprehensive')
			matched_unames = [x.username.lower() for x in policy.query(username_search_term.lower(),
																	   provided=IUser.providedBy)]
			filter_usernames = {x for x in filter_usernames if x in matched_unames}
			result['FilteredTotalItemCount'] = len(filter_usernames)

		result['TotalNonNullItemCount'] = len(context)

		grade_column_set = {x.lower() for x in grade_column}
		result['FilteredTotalNonNullItemCount'] = len( grade_column_set & set(filter_usernames) )

		if sort_name:
			items_factory = list
			try:
				items_iter = getattr(self, '_do_sort_' + sort_name)(filter_usernames, sort_reverse)
			except AttributeError:
				# We're not silently ignoring because in the past
				# we've had clients send in the wrong value for a long time
				# before anybody noticed
				raise hexc.HTTPBadRequest("Unsupported sort option")
		else:
			# Leave as a dict, and don't generate
			# placeholders (unless they filtered, always generate placeholders
			# if they filter)
			items_iter = self._do_sort_username(filter_usernames,
												sort_reverse,
												placeholder=filtered)

		batchAround = None
		batchAroundTest = None
		# We must defer reading these until after we sort, sometimes
		# sorting will change them, if batchAroundCreator is given
		batch_size, batch_start = self._get_batch_size_start()
		if batch_size is not None:
			if self.request.params.get( 'batchAround', '' ):
				batchAround = self.request.params.get( 'batchAround' )
				batchAroundTest = lambda key_value: to_external_ntiid_oid( key_value[1] ) == batchAround
			elif self.request.params.get( 'batchAroundCreator', ''):
				# This branch is often handled during sorting, but sometimes
				# we have to defer it until now.
				batchAround = self.request.params.get('batchAroundCreator').lower()
				batchAroundTest = lambda key_value: key_value[0].lower() == batchAround

			if batchAroundTest:
				items_iter = self._batch_on_item(items_iter, batchAroundTest)
				batch_size, batch_start = self._get_batch_size_start()

		if (batch_size is not None and batch_start is not None) or items_factory is list:
			self._batch_tuple_iterable(result, items_iter,
									   batch_size=batch_size,
									   batch_start=batch_start,
									   selector=lambda x: x)
		else:
			result[ITEMS] = items_factory(items_iter)

		return result
