#!/usr/local/bin/python
# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

from goflow.runtime.models import ProcessInstance, WorkItem
from goflow.common.logger import Log; log = Log('goflow.workflow.managers')

class ProcessManager(models.Manager):
    '''Custom model manager for Process
    '''

    def start(self, process_name, user, item, title=None):
        '''
        Returns a workitem given the name of a preexisting enabled Process
        instance, while passing in the id of the user, the contenttype
        object and the title.

        :type process_name: string
        :param process_name: a name of a process. e.g. 'leave'
        :type user: User
        :param user: an instance of django.contrib.auth.models.User,
                     typically retrieved through a request object.
        :type item: ContentType
        :param item: a content_type object e.g. an instance of LeaveRequest
        :type: title: string
        :param title: title of new ProcessInstance instance (optional)
        :rtype: WorkItem
        :return: a newly configured workitem sent to auto_user,
                 a target_user, or ?? (roles).

        usage::

            wi = Process.objects.start(process_name='leave',
                                       user=admin, item=leaverequest1)

        '''
        process = self.get(title=process_name, enabled=True)
        if not title or (title=='instance'):
            title = '%s %s' % (process_name, str(item))
        instance = ProcessInstance.objects.add(user, title, item)
        instance.process = process
        # instance running
        instance.set_status('running')
        instance.save()

        workitem = WorkItem.objects.create(instance=instance, user=user,
                                           activity=process.begin)
        log.event('created by ' + user.username, workitem)
        log('process:', process_name, 'user:', user.username, 'item:', item)

        if process.begin.autostart:
            log('run auto activity', process.begin.title, 'workitem:', workitem)
            auto_user = User.objects.get(username=settings.WF_USER_AUTO)
            workitem.activate(actor=auto_user)

            if workitem.run_activity_app():
                log('workitem.run_activity_app:', workitem)
                workitem.complete(actor=auto_user)
            return workitem

        if process.begin.push_application:
            target_user = workitem.exec_push_application()
            #target_user = workitem.push_to_next_user()
            log('application pushed to user', target_user.username)
            workitem.user = target_user
            workitem.save()
            log.event('assigned to '+target_user.username, workitem)
            #notify_if_needed(user=target_user)
        else:
            # set pull roles; useful (in activity too)?
            workitem.pull_roles = workitem.activity.roles.all()
            workitem.save()
            #notify_if_needed(roles=workitem.pull_roles)

        return workitem

    #TODO: also not too happy about this one.
    def process_is_enabled(self, title):
        '''
        Determines given a title if a process is enabled or otherwise

        :rtype: bool

        usage::

            if Process.objects.process_is_enabled('leave1'):
                # do something

        '''
        return self.get(title=title).enabled

    def add(self, title, description=''):
        '''
        Creates, saves, and returns a Process instance
        and adds an intital activity to it.

        :type title: string
        :param title: the title of the new Process instance.
        :type description: string
        :param description: an optional description of the new Process instance.
        :rtype: Process
        :return: a new (saved) Process instance.

        usage::

            process1 = Process.objects.add(title='process1')
        '''
        process = self.create(title=title, description=description)
        process.begin = models.get_model('workflow', 'Activity').objects.create(
            title='initial', process=process)
        #process.end = Activity.objects.create(title='final', process=process)
        process.save()
        return process

    #TODO: not too happy with the naming or place of the function here..
    def check_start_instance_perm(self, process_name, user):
        '''
        Checks whether a process is enabled and whether the user has permission
        to instantiate it; raises exceptions if not the case, returns None otherwise.

        :type process_name: string
        :param process_name: a name of a process. e.g. 'leave'
        :type user: User
        :param user: an instance of django.contrib.auth.models.User,
                     typically retrieved through a request object.
        :rtype:
        :return: passes silently if checks are met,
                 raises exceptions otherwise.

        usage::

            Process.objects.check_start_instance_perm(process_name='leave1', user=admin)

        '''
        if not self.process_is_enabled(process_name):
            raise Exception('process %s disabled.' % process_name)

        if user.has_perm("workflow.can_instantiate"):
            lst = user.groups.filter(name=process_name)
            if lst.count()==0 or \
               (lst[0].permissions.filter(codename='can_instantiate').count() == 0):
                raise Exception('permission needed to instantiate process %s.' % process_name)
        else:
            raise Exception('permission needed.')
        return
