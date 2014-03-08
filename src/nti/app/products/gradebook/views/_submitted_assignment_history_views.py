#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)



from zope import component
from zope import interface


from pyramid.view import view_config
from pyramid import httpexceptions as hexc


from natsort import natsorted
from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.appserver.interfaces import IIntIdUserSearchPolicy
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import is_instructed_by_name
from nti.dataserver.interfaces import IEnumerableEntityContainer
from nti.dataserver.interfaces import IUser
from nti.dataserver.users import Entity
from nti.dataserver.users.interfaces import IFriendlyNamed
from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.oids import to_external_ntiid_oid

from ..interfaces import ISubmittedAssignmentHistoryBase
from ..interfaces import IGrade

from nti.dataserver import authorization as nauth
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.contenttypes.courses.interfaces import ICourseInstance

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
		A dictionary from student username to submission history item
		(or possibly null)

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


	def _make_force_placeholder_usernames(self, filter_usernames):
		batch_size, batch_start = self._get_batch_size_start()
		if batch_size is None or batch_start is None:
			return

		for x in self._BATCH_LINK_DROP_PARAMS:
			if self.request.params.get(x):
				return

		forced_placeholder_usernames = None

		end_idx = batch_start + batch_size
		if batch_start > len(filter_usernames):
			# ignore everyone!
			forced_placeholder_usernames = set(filter_usernames)
		elif batch_start > 0:
			# Before the batch
			forced_placeholder_usernames = filter_usernames[0:batch_start - 1]
			# after the batch. Note that this is fine even if end_idx is greater than len
			forced_placeholder_usernames.extend( filter_usernames[end_idx:] )
			forced_placeholder_usernames = set(forced_placeholder_usernames )
		else: # batch_start == 0
			# after the batch
			forced_placeholder_usernames = set( filter_usernames[end_idx:] )

		return forced_placeholder_usernames

	def __call__(self):
		request = self.request
		context = request.context
		username = request.authenticated_userid
		course = ICourseInstance(context)

		if not is_instructed_by_name(course, username):
			raise hexc.HTTPForbidden()

		result = LocatedExternalDict()
		column = context.__parent__
		result.__parent__ = column
		result.__name__ = context.__name__

		filter_name = self.request.params.get('filter')
		sort_name = self.request.params.get('sortOn')
		username_search_term = self.request.params.get('usernameSearchTerm')

		if filter_name in ('LegacyEnrollmentStatusForCredit', 'LegacyEnrollmentStatusOpen'):
			# Get the set of usernames. Right now, we have a direct
			# dependency on the legacy course instance, so we need some better
			# abstractions around this. This will break when we have
			# non-legacy courses
			everyone = course.legacy_community
			restricted_id = course.LegacyScopes['restricted']
			restricted = Entity.get_entity(restricted_id) if restricted_id else None

			restricted_usernames = set(IEnumerableEntityContainer(restricted).iter_usernames()) if restricted is not None else set()
			everyone_usernames = set(IEnumerableEntityContainer(everyone).iter_usernames())
			# instructors are also a member of the restricted set,
			# so take them out (otherwise the count will be wrong)
			if filter_name == 'LegacyEnrollmentStatusForCredit':
				filter_usernames = restricted_usernames - {x.id for x in course.instructors}
			elif filter_name == 'LegacyEnrollmentStatusOpen':
				filter_usernames = everyone_usernames - restricted_usernames - {x.id for x in course.instructors}

			result['TotalItemCount'] = ICourseEnrollments(course).count_enrollments()
			result['FilteredTotalItemCount'] = len(filter_usernames)

			if username_search_term:
				policy = component.getAdapter(self.remoteUser, IIntIdUserSearchPolicy, name='comprehensive')
				matched_unames = [x.username for x in policy.query(username_search_term.lower(),
																   provided=IUser.providedBy)]
				filter_usernames = {x for x in filter_usernames if x in matched_unames}
				result['FilteredTotalItemCount'] = len(filter_usernames)


			# Because the items() method returns things in the order that they are
			# listed in usernames, we can sort usernames first to get the correct
			# order. This is especially helpful when paging as we can consume the part
			# of the generator needed.
			items_factory = dict # don't use an ordered dict if we don't sort
			items_iter = None
			sort_reverse = self.request.params.get('sortOrder', 'ascending') == 'descending'
			batch_size, batch_start = self._get_batch_size_start()

			if sort_name == 'realname':
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
				items_factory = list
				items_iter = context.items(usernames=filter_usernames,
										   placeholder=None,
										   forced_placeholder_usernames=self._make_force_placeholder_usernames(filter_usernames))
			elif sort_name == 'dateSubmitted':
				# We can optimize this by sorting on the created dates of the grade
				# in the gradebook; those should correspond one-to-one to submitted
				# assignments---we assume as much when we set TotalNonNullItemCount.
				# This will let us apply the force-placeholder trick
				filter_usernames = sorted(filter_usernames)
				all_items = context.items(usernames=filter_usernames,placeholder=None)
				items_iter = sorted(all_items,
									key=lambda x: x[1].createdTime if x[1] else 0,
									reverse=sort_reverse)
				items_factory = list
			elif sort_name == 'feedbackCount':
				# We can optimize this by sorting on the value of the grades directly
				# in the gradebook. This will let us apply the force-placeholder trick
				filter_usernames = sorted(filter_usernames)
				all_items = context.items(usernames=filter_usernames,placeholder=None)
				items_iter = sorted(all_items,
									key=lambda x: x[1].FeedbackCount if x[1] else 0,
									reverse=sort_reverse)
				items_factory = list
			elif sort_name == 'gradeValue':
				filter_usernames = sorted(filter_usernames)
				all_items = context.items(usernames=filter_usernames,placeholder=None)
				items_iter = natsorted(all_items,
									   key=lambda x: IGrade(x[1]).value if x[1] else 0, # this is pretty inefficient
									   )
				if sort_reverse:
					items_iter = reversed(items_iter)
				items_factory = list
			elif sort_name == 'username' or not sort_name:
				# Default to sorting based on usernames
				items_factory = list if sort_name else dict

				filter_usernames = sorted(filter_usernames,
										  reverse=sort_reverse)

				items_iter = context.items(usernames=filter_usernames,
										   placeholder=None,
										   forced_placeholder_usernames=self._make_force_placeholder_usernames(filter_usernames))
			elif sort_name: # pragma: no cover
				# We're not silently ignoring because in the past
				# we've had clients send in the wrong value for a long time
				# before anybody noticed
				raise hexc.HTTPBadRequest("Unsupported sort option")





			batchAround = None
			batchAroundKey = None
			# TODO: Similar to code in ugd_query_views
			if batch_size is not None:
				if self.request.params.get( 'batchAround', '' ):
					batchAround = self.request.params.get( 'batchAround' )
					batchAroundKey = lambda key_value: to_external_ntiid_oid( key_value[1] )
				elif self.request.params.get( 'batchAroundCreator', ''):
					# This branch we could optimize based on the usernames array above
					# and combine with the force-placeholder trick
					batchAround = self.request.params.get('batchAroundCreator').lower()
					batchAroundKey = lambda key_value: key_value[0].lower()

			if batchAround is not None:
				items_factory = list
				# Ok, they have requested that we compute a beginning index for them.
				# We do this by materializing the list in memory and walking through
				# to find the index of the requested object.
				batch_start = None # ignore input
				result_list = []
				match_index = None
				for i, key_value in enumerate(items_iter):
					result_list.append( key_value )

					# Only keep testing until we find what we need
					# TODO: We should be able to break under some
					# circumstances, yes? If the items_iter is a generator,
					# that would be benificial
					if batch_start is None:
						if batchAroundKey( key_value ) == batchAround:
							batch_start = max( 0, i - (batch_size // 2) - 1 )
							match_index = i

				items_iter = result_list
				if batch_start is None:
					# Well, we got here without finding the matching value.
					# So return an empty page.
					batch_start = len(result_list)
				elif match_index <= batch_start + batch_size:
					# For very small batches, when the match is at
					# the beginning of the list (typically),
					# we could wind up returning a list that doesn't include
					# the around value. Do our best to make sure that
					# doesn't happen.
					batch_start = max( 0, match_index - (batch_size // 2))
			if (batch_size is not None and batch_start is not None) or items_factory is list:
				self._batch_tuple_iterable(result, items_iter,
										   batch_size=batch_size,
										   batch_start=batch_start,
										   selector=lambda x: x)
			else:
				result['Items'] = items_factory(items_iter)

		else:
			# Everything
			result['Items'] = dict(context)
			result['TotalItemCount'] = len(result['Items'])
			result['FilteredTotalItemCount'] = result['TotalItemCount']

		result['TotalNonNullItemCount'] = len(context)

		return result
