# -*- coding: utf-8 -*-
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
import logging
from parser import VkontaktePhotosParser
import re

from vkontakte_api.decorators import fetch_all
from vkontakte_api.mixins import CountOffsetManagerMixin, AfterBeforeManagerMixin, OwnerableModelMixin, LikableModelMixin
from vkontakte_api.models import VkontakteTimelineManager, VkontakteModel, VkontakteCRUDModel, VkontaktePKModel
from vkontakte_comments.mixins import CommentableModelMixin

from vkontakte_users.models import User
log = logging.getLogger('vkontakte_photos')

ALBUM_PRIVACY_CHOCIES = (
    (0, u'Все пользователи'),
    (1, u'Только друзья'),
    (2, u'Друзья и друзья друзей'),
    (3, u'Только я')
)


class AlbumRemoteManager(AfterBeforeManagerMixin):

    methods_namespace = 'photos'
    version = 5.27
    timeline_force_ordering = True

    def get_timeline_date(self, instance):
        return instance.updated or instance.created or timezone.now()

    @transaction.commit_on_success
    def fetch(self, user=None, group=None, owner=None, ids=None, need_covers=False, **kwargs):
        if not (user or group):
            #raise ValueError("You must specify user of group, which albums you want to fetch")
            if not owner:
                raise ValueError("You must specify owner, which albums you want to fetch")

        if ids and not isinstance(ids, (tuple, list)):
            raise ValueError("Attribute 'ids' should be tuple or list")

        if not owner:
            owner = user or group

        kwargs['owner_id'] = self.model.get_owner_remote_id(owner)

        # need_covers
        # 1 - будет возвращено дополнительное поле thumb_src. По умолчанию поле thumb_src не возвращается.
        kwargs['need_covers'] = int(need_covers)

        # aids
        # перечисленные через запятую ID альбомов.
        if ids:
            kwargs.update({'album_ids': ','.join(map(str, ids))})

        return super(AlbumRemoteManager, self).fetch(**kwargs)


class PhotoRemoteManager(CountOffsetManagerMixin, AfterBeforeManagerMixin):

    methods_namespace = 'photos'
    version = 5.27
    timeline_cut_fieldname = 'date'
    timeline_force_ordering = True

    @transaction.commit_on_success
    def fetch(self, album, ids=None, extended=False, photo_sizes=False, rev=0, **kwargs):
        if ids and not isinstance(ids, (tuple, list)):
            raise ValueError("Attribute 'ids' should be tuple or list")
        # TODO: it seems rev attribute make no sence for order of response
        if rev == 1 and (after or before):
            raise ValueError("Attribute `rev` should be equal to 0 with defined `after` attribute")

        kwargs.update({
            #'album_id': album.remote_id.split('_')[1],
            'extended': int(extended),
            # photo_sizes
            # 1 - позволяет получать все размеры фотографий.
            'photo_sizes': int(photo_sizes),
        })

        if album:
            kwargs['album_id'] = album.remote_id
            kwargs['owner_id'] = album.owner_remote_id

        if ids:
            kwargs.update({'photo_ids': ','.join(map(str, ids))})

        kwargs['rev'] = int(rev)

        # TODO: добавить поля
        # feed
        # Unixtime, который может быть получен методом newsfeed.get в поле date, для получения всех фотографий загруженных пользователем в определённый день либо на которых пользователь был отмечен. Также нужно указать параметр uid пользователя, с которым произошло событие.
        # feed_type
        # Тип новости получаемый в поле type метода newsfeed.get, для получения только загруженных пользователем фотографий, либо только фотографий, на которых он был отмечен. Может принимать значения photo, photo_tag.

        return super(PhotoRemoteManager, self).fetch(**kwargs)


@python_2_unicode_compatible
class Album(OwnerableModelMixin, VkontaktePKModel):
    thumb_id = models.PositiveIntegerField()
    thumb_src = models.CharField(u'Обложка альбома', max_length='200')

    title = models.CharField(max_length='200')
    description = models.TextField()

    created = models.DateTimeField(null=True, db_index=True)
    updated = models.DateTimeField(null=True, db_index=True)

    size = models.PositiveIntegerField(u'Кол-во фотографий')
    privacy = models.PositiveIntegerField(u'Уровень доступа к альбому', null=True, choices=ALBUM_PRIVACY_CHOCIES)

    objects = models.Manager()
    remote = AlbumRemoteManager(remote_pk=('remote_id',), methods={
        'get': 'getAlbums',
#        'edit': 'editAlbum',
    })

    class Meta:
        verbose_name = u'Альбом фотографий Вконтакте'
        verbose_name_plural = u'Альбомы фотографий Вконтакте'

    def __str__(self):
        return self.title

    @property
    def slug(self):
        return 'album%s_%s' % (self.owner_remote_id, self.remote_id)

    @transaction.commit_on_success
    def fetch_photos(self, *args, **kwargs):
        return Photo.remote.fetch(album=self, *args, **kwargs)


class Photo(OwnerableModelMixin, LikableModelMixin, CommentableModelMixin, VkontaktePKModel):

    comments_remote_related_name = 'photo_id'
    likes_remote_type = 'photo'

    album = models.ForeignKey(Album, verbose_name=u'Альбом', related_name='photos')
    user = models.ForeignKey(User, verbose_name=u'Автор фотографии', null=True, related_name='photos_author')

    #src = models.CharField(u'Иконка', max_length='200')
    #src_big = models.CharField(u'Большая', max_length='200')
    #src_small = models.CharField(u'Маленькая', max_length='200')
    #src_xbig = models.CharField(u'Большая X', max_length='200')
    #src_xxbig = models.CharField(u'Большая XX', max_length='200')

    photo_75 = models.CharField(u'Иконка', max_length='200')
    photo_130 = models.CharField(u'Большая', max_length='200')
    photo_604 = models.CharField(u'Маленькая', max_length='200')
    photo_807 = models.CharField(u'Большая X', max_length='200')
    photo_1280 = models.CharField(u'Большая XX', max_length='200')
    photo_2560 = models.CharField(u'Большая XXX', max_length='200')

    width = models.PositiveIntegerField(null=True)
    height = models.PositiveIntegerField(null=True)

    actions_count = models.PositiveIntegerField(u'Комментариев', default=0)
    tags_count = models.PositiveIntegerField(u'Тегов', default=0)

    text = models.TextField()

    date = models.DateTimeField(db_index=True)

    objects = models.Manager()
    remote = PhotoRemoteManager(remote_pk=('remote_id',), methods={
        'get': 'get',
    })

    class Meta:
        verbose_name = u'Фотография Вконтакте'
        verbose_name_plural = u'Фотографии Вконтакте'

    @property
    def src(self):
        return self.photo_130

    @property
    def created(self):
        return self.date

    @property
    def slug(self):
        return 'photo%s_%s' % (self.owner_remote_id, self.remote_id)

    def parse(self, response):
        super(Photo, self).parse(response)

        # counters
        for field_name in ['tags']:  # ['likes', 'comments', 'tags']:
            if field_name in response and 'count' in response[field_name]:
                setattr(self, '%s_count' % field_name, response[field_name]['count'])

        if not self.likes_count:
            self.likes_count = 0

        if not self.comments_count:
            self.comments_count = 0

        self.actions_count = self.likes_count + self.comments_count

        if 'user_id' in response:
            self.user = User.objects.get_or_create(remote_id=response['user_id'])[0]

        # try:
        #    self.album = Album.objects.get(remote_id=self.get_remote_id(response['aid']))
        # except Album.DoesNotExist:
        #    raise Exception('Impossible to save photo for unexisted album %s' % (self.get_remote_id(response['aid']),))
        self.album_id = response.get('album_id', None)

    def fetch_comments_parser(self):
        '''
        Fetch total ammount of comments
        TODO: implement fetching comments
        '''
        post_data = {
            'act': 'photo_comments',
            'al': 1,
            'offset': 0,
            'photo': '%s_%s' % (self.owner_remote_id, self.remote_id),
        }
        parser = VkontaktePhotosParser().request('/al_photos.php', data=post_data)

        self.comments_count = len(parser.content_bs.findAll('div', {'class': 'clear_fix pv_comment '}))
        self.save()

    def fetch_likes_parser(self):
        '''
        Fetch total ammount of likes
        TODO: implement fetching users who likes
        '''
        post_data = {
            'act': 'a_get_stats',
            'al': 1,
            'list': 'album%s_%s' % (self.owner_remote_id, self.album.remote_id),
            'object': 'photo%s_%s' % (self.owner_remote_id, self.remote_id),
        }
        parser = VkontaktePhotosParser().request('/like.php', data=post_data)

        values = re.findall(r'value="(\d+)"', parser.html)
        if len(values):
            self.likes_count = int(values[0])
            self.save()
