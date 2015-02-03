# -*- coding: utf-8 -*-
from django.test import TestCase
from django.utils import timezone
from os.path import join, dirname

import mock
from vkontakte_groups.factories import GroupFactory

import simplejson as json
from vkontakte_comments.models import Comment
from vkontakte_users.factories import UserFactory, User
from vkontakte_users.tests import user_fetch_mock
from . factories import AlbumFactory, PhotoFactory
from . models import Album, Photo


GROUP_ID = 16297716
ALBUM_ID = 154228728
PHOTO_ID = 280118215

GROUP_CRUD_ID = 59154616
PHOTO_CRUD_ID = 321155660
ALBUM_CRUD_ID = 180124643
USER_AUTHOR_ID = 201164356


class VkontaktePhotosTest(TestCase):

    def setUp(self):
        self.objects_to_delete = []

    def tearDown(self):
        for object in self.objects_to_delete:
            object.delete(commit_remote=True)

    def test_fetch_group_albums(self):

        group = GroupFactory(remote_id=GROUP_ID)

        self.assertEqual(Album.objects.count(), 0)

        albums = group.fetch_albums()

        self.assertGreater(len(albums), 0)
        self.assertEqual(Album.objects.count(), len(albums))
        self.assertEqual(albums[0].owner, group)

        # check force ordering
        self.assertItemsEqual(albums, Album.objects.order_by('-updated'))

        # testing `after` parameter
        after = Album.objects.order_by('-updated')[10].updated

        albums_count = Album.objects.count()
        Album.objects.all().delete()
        self.assertEqual(Album.objects.count(), 0)

        albums = group.fetch_albums(after=after)
        self.assertEqual(albums.count(), Album.objects.count())
        self.assertLess(albums.count(), albums_count)

        # testing `before` parameter
        before = Album.objects.order_by('-updated')[5].updated

        albums_count = Album.objects.count()
        Album.objects.all().delete()
        self.assertEqual(Album.objects.count(), 0)

        albums = group.fetch_albums(before=before, after=after)
        self.assertEqual(albums.count(), Album.objects.count())
        self.assertLess(albums.count(), albums_count)

    def test_fetch_group_photos(self):

        group = GroupFactory(remote_id=GROUP_ID)
        album = AlbumFactory(remote_id=ALBUM_ID, owner=group)

        self.assertEqual(Photo.objects.count(), 0)

        photos = album.fetch_photos(extended=True)

        self.assertGreater(len(photos), 0)
        self.assertEqual(Photo.objects.count(), len(photos))
        self.assertEqual(photos[0].owner, group)
        self.assertEqual(photos[0].album, album)
        self.assertGreater(photos[0].likes_count, 0)
        self.assertGreater(photos[0].comments_count, 0)

        # testing `after` parameter
        after = Photo.objects.order_by('-date')[4].date

        photos_count = Photo.objects.count()
        Photo.objects.all().delete()
        self.assertEqual(Photo.objects.count(), 0)

        photos = album.fetch_photos(after=after)
        self.assertEqual(photos.count(), Photo.objects.count())
        self.assertLess(photos.count(), photos_count)

        # testing `before` parameter
        before = Photo.objects.order_by('-date')[2].date

        photos_count = Photo.objects.count()
        Photo.objects.all().delete()
        self.assertEqual(Photo.objects.count(), 0)

        photos = album.fetch_photos(before=before, after=after)
        self.assertEqual(photos.count(), Photo.objects.count())
        self.assertLess(photos.count(), photos_count)

    @mock.patch('vkontakte_users.models.User.remote._fetch', side_effect=user_fetch_mock)
    def test_fetch_photo_comments(self, *kwargs):

        group = GroupFactory(remote_id=GROUP_ID)
        album = AlbumFactory(remote_id=ALBUM_ID, owner=group)
        photo = PhotoFactory(remote_id=PHOTO_ID, album=album, owner=group)

        comments = photo.fetch_comments(count=20, sort='desc')
        self.assertEqual(comments.count(), photo.comments.count())
        self.assertEqual(comments.count(), 20)

        # testing `after` parameter
        after = Comment.objects.order_by('date')[0].date

        comments_count = Comment.objects.count()
        Comment.objects.all().delete()
        self.assertEqual(Comment.objects.count(), 0)

        comments = photo.fetch_comments(after=after, sort='desc')
        self.assertEqual(comments.count(), Comment.objects.count())
        self.assertEqual(comments.count(), photo.comments.count())
        self.assertEqual(comments.count(), comments_count)

        # testing `all` parameter
        Comment.objects.all().delete()
        self.assertEqual(Comment.objects.count(), 0)

        comments = photo.fetch_comments(all=True)
        self.assertEqual(comments.count(), Comment.objects.count())
        self.assertEqual(comments.count(), photo.comments.count())
        self.assertGreater(photo.comments.count(), comments_count)

    @mock.patch('vkontakte_users.models.User.remote._fetch', side_effect=user_fetch_mock)
    def test_fetch_photo_likes(self, *kwargs):

        group = GroupFactory(remote_id=GROUP_ID)
        album = AlbumFactory(remote_id=ALBUM_ID, owner=group)
        photo = PhotoFactory(remote_id=PHOTO_ID, album=album, owner=group)

        self.assertEqual(photo.likes_count, 0)
        users_initial = User.objects.count()

        users = photo.fetch_likes(all=True)

        self.assertGreater(photo.likes_count, 0)
        self.assertEqual(photo.likes_count, len(users))
        self.assertEqual(photo.likes_count, User.objects.count() - users_initial)
        self.assertEqual(photo.likes_count, photo.likes_users.count())

    def test_fetch_photo_likes_parser(self):

        group = GroupFactory(remote_id=GROUP_ID)
        album = AlbumFactory(remote_id=ALBUM_ID, owner=group)
        photo = PhotoFactory(remote_id=PHOTO_ID, album=album, owner=group)

        self.assertEqual(photo.likes_count, 0)
        photo.fetch_likes_parser()
        self.assertGreater(photo.likes_count, 0)

    def test_fetch_photo_comments_parser(self):

        group = GroupFactory(remote_id=GROUP_ID)
        album = AlbumFactory(remote_id=ALBUM_ID, owner=group)
        photo = PhotoFactory(remote_id=PHOTO_ID, album=album, owner=group)

        #self.assertEqual(photo.comments_count, 0)
        photo.fetch_comments_parser()
        self.assertGreater(photo.comments_count, 0)

    def test_parse_album(self):

        response = '''{"response":[{"id":16178407,"thumb_id":"96509883","owner_id":6492,"title":"qwerty",
            "description":"desc","created":"1298365200","updated":"1298365201","size":"3",
            "privacy":"3"},{"id":"17071606","thumb_id":"98054577","owner_id":-6492,
            "title":"","description":"","created":"1204576880","updated":"1229532461",
            "size":"3","privacy":"0"}]}
            '''
        instance = Album()
        owner = UserFactory(remote_id=6492)
        instance.parse(json.loads(response)['response'][0])
        instance.save()

        self.assertEqual(instance.remote_id, 16178407)
        self.assertEqual(instance.thumb_id, 96509883)
        self.assertEqual(instance.owner, owner)
        self.assertEqual(instance.title, 'qwerty')
        self.assertEqual(instance.description, 'desc')
        self.assertEqual(instance.size, 3)
        self.assertEqual(instance.privacy, 3)
        self.assertIsNotNone(instance.created)
        self.assertIsNotNone(instance.updated)

        instance = Album()
        group = GroupFactory(remote_id=6492)
        instance.parse(json.loads(response)['response'][1])
        instance.save()

        self.assertEqual(instance.remote_id, 17071606)
        self.assertEqual(instance.owner, group)

    def test_parse_photo(self):

        response = '''{"response":[{"id":"146771291","album_id":"100001227","owner_id":6492,
            "photo_130":"http://cs9231.vkontakte.ru/u06492/100001227/m_7875d2fb.jpg",
            "text":"test","user_id":6492,"width":10,"height":10,
            "date":"1298365200"},

            {"id":"146772677","album_id":"100001227","owner_id":-6492,
            "photo_130":"http://cs9231.vkontakte.ru/u06492/100001227/m_fd092958.jpg",
            "text":"test","user_id":6492,"width":10,"height":10,
            "date":"1260887080"}]}
            '''
        instance = Photo()
        owner = UserFactory(remote_id=6492)
        album = AlbumFactory(remote_id=100001227, owner=owner)
        instance.parse(json.loads(response)['response'][0])
        instance.save()

        self.assertEqual(instance.remote_id, 146771291)
        self.assertEqual(instance.album, album)
        self.assertEqual(instance.owner, owner)
        self.assertEqual(instance.src, instance.photo_130)
        self.assertEqual(instance.src, 'http://cs9231.vkontakte.ru/u06492/100001227/m_7875d2fb.jpg')
        self.assertEqual(instance.text, 'test')
        self.assertEqual(instance.width, 10)
        self.assertEqual(instance.height, 10)
        self.assertIsNotNone(instance.created)

        instance = Photo()
        group = GroupFactory(remote_id=6492)
        #album = AlbumFactory(remote_id=100001227, owner=owner)
        instance.parse(json.loads(response)['response'][1])
        instance.save()

        self.assertEqual(instance.remote_id, 146772677)
        self.assertEqual(instance.album, album)
        self.assertEqual(instance.owner, group)

    def test_parse_comment(self):

        response = '''{"response":[21, {"date": 1387173931, "message": "[id94721323|\u0410\u043b\u0435\u043d\u0447\u0438\u043a], \u043d\u0435 1 \u0430 3 \u0431\u0430\u043d\u043a\u0430 5 \u043b\u0438\u0442\u0440\u043e\u0432 =20 \u0431\u0430\u043b\u043b\u043e\u0432", "from_id": 232760293, "likes": {"count": 1, "can_like": 1, "user_likes": 0}, "id": 91121},
            {"date": 1386245221, "message": "\u0410 1\u043b. \u0432 \u043f\u043e\u0434\u0430\u0440\u043e\u043a,\u0431\u043e\u043d\u0443\u0441 +))))", "from_id": 94721323, "likes": {"count": 0, "can_like": 1, "user_likes": 0}, "id": 88976},
            {"date": 1354592120, "message": "\u0445\u0430\u0445<br>", "from_id": 138571769, "likes": {"count": 0, "can_like": 1, "user_likes": 0}, "cid": 50392}]}
        '''
        group = GroupFactory(remote_id=GROUP_ID)
        album = AlbumFactory(remote_id=ALBUM_ID, owner=group)
        photo = PhotoFactory(remote_id=PHOTO_ID, album=album, owner=group)
        instance = Comment(object=photo)
        instance.parse(json.loads(response)['response'][1])
        instance.save()

        self.assertEqual(instance.remote_id, '-%s_91121' % GROUP_ID)
        self.assertEqual(instance.object, photo)
        self.assertEqual(instance.author.remote_id, 232760293)
        self.assertGreater(len(instance.text), 10)
        self.assertIsNotNone(instance.date)

    def test_comment_crud_methods(self):
        group = GroupFactory(remote_id=GROUP_CRUD_ID)
        album = AlbumFactory(remote_id=ALBUM_CRUD_ID, owner=group)
        photo = PhotoFactory(remote_id=PHOTO_CRUD_ID, owner=group, album=album)

        def assert_local_equal_to_remote(comment):
            comment_remote = Comment.remote.fetch_by_object(object=comment.object).get(remote_id=comment.remote_id)
            self.assertEqual(comment_remote.remote_id, comment.remote_id)
            self.assertEqual(comment_remote.text, comment.text)
            self.assertEqual(comment_remote.author, comment.author)

        # try to delete comments from prev tests
        for comment in Comment.remote.fetch_by_object(object=photo):
            comment.delete(commit_remote=True)
        # checks there is no remote and local comments
        comments = Comment.remote.fetch_by_object(object=photo)
        self.assertEqual(Comment.objects.count(), 0, 'Error: There are %s comments from previous test. Delete them manually here %s' % (
            comments.count(), photo.get_url()))

        # create
        comment = Comment(text='Test comment', object=photo, author=group, date=timezone.now())
        comment.save(commit_remote=True)
        self.objects_to_delete += [comment]

        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(comment.author, group)
        self.assertNotEqual(len(comment.remote_id), 0)
        assert_local_equal_to_remote(comment)

        # create by manager
        comment = Comment.objects.create(
            text='Test comment created by manager', object=photo, author=group, date=timezone.now(), commit_remote=True)
        self.objects_to_delete += [comment]
        self.assertEqual(Comment.objects.count(), 2)

        self.assertEqual(Comment.objects.count(), 2)
        self.assertEqual(comment.author, group)
        self.assertNotEqual(len(comment.remote_id), 0)
        assert_local_equal_to_remote(comment)

        # update
        comment.text = 'Test comment updated'
        comment.save(commit_remote=True)

        self.assertEqual(Comment.objects.count(), 2)
        assert_local_equal_to_remote(comment)

        # delete
        comment.delete(commit_remote=True)

        self.assertEqual(Comment.objects.count(), 2)
        self.assertTrue(comment.archived)
        self.assertEqual(Comment.remote.fetch_by_object(
            object=comment.object).filter(remote_id=comment.remote_id).count(), 0)

        # restore
        comment.restore(commit_remote=True)
        self.assertFalse(comment.archived)

        self.assertEqual(Comment.objects.count(), 2)
        assert_local_equal_to_remote(comment)


class VkontakteUploadPhotos(TestCase):

    def setUp(self):
        self.objects_to_delete = []

        path = dirname(__file__)
        path = join(path, 'tests')

        file1 = join(path, 'test_photo1.jpg')
        file2 = join(path, 'test_photo2.png')

        self.files = [file1, file2]

    def tearDown(self):
        for object in self.objects_to_delete:
            object.delete(commit_remote=True)

    def test_upload_to_group_album(self):
        group = GroupFactory(remote_id=59154616)
        album = AlbumFactory(remote_id=209832918, owner=group)

        caption = 'test_upload'
        photos = album.upload_photos(self.files, caption=caption)

        self.objects_to_delete += photos  # delete photos

        self.assertEqual(len(photos), 2)
        self.assertEqual(photos[0].text, caption)

    def test_upload_to_user_album(self):
        user = UserFactory(remote_id=201164356)
        album = AlbumFactory(remote_id=209873101, owner=user)

        caption = 'test_upload'
        photos = album.upload_photos(self.files, caption=caption)

        self.objects_to_delete += photos  # delete photos

        self.assertEqual(len(photos), 2)
        self.assertEqual(photos[0].text, caption)
