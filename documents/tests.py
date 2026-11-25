import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import Document, DocumentShare
from .sanitizer import sanitize_html

User = get_user_model()


class DocumentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='password123',
        )

    def test_document_creation_and_ownership(self):
        doc = Document.objects.create(
            title='Project Proposal',
            content='Initial draft content.',
            owner=self.user,
        )
        self.assertEqual(doc.title, 'Project Proposal')
        self.assertEqual(doc.content, 'Initial draft content.')
        self.assertEqual(doc.owner, self.user)
        self.assertIsNotNone(doc.created_at)
        self.assertIsNotNone(doc.updated_at)
        self.assertEqual(str(doc), 'Project Proposal')
        self.assertIn(doc, self.user.owned_documents.all())

    def test_document_default_content_and_ordering(self):
        doc1 = Document.objects.create(title='First Document', owner=self.user)
        doc2 = Document.objects.create(title='Second Document', owner=self.user)

        self.assertEqual(doc1.content, '')

        # Ordering by -updated_at puts most recently updated first
        doc1.title = 'Updated First Document'
        doc1.save()

        documents = list(Document.objects.all())
        self.assertEqual(documents[0], doc1)
        self.assertEqual(documents[1], doc2)


class DocumentShareModelTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner_user',
            email='owner@example.com',
            password='password123',
        )
        self.colleague = User.objects.create_user(
            username='colleague_user',
            email='colleague@example.com',
            password='password123',
        )
        self.editor = User.objects.create_user(
            username='editor_user',
            email='editor@example.com',
            password='password123',
        )
        self.document = Document.objects.create(
            title='Collaborative Spec',
            owner=self.owner,
        )

    def test_successful_sharing(self):
        share_viewer = DocumentShare.objects.create(
            document=self.document,
            user=self.colleague,
        )
        self.assertEqual(share_viewer.permission, DocumentShare.Permission.VIEWER)
        self.assertEqual(share_viewer.document, self.document)
        self.assertEqual(share_viewer.user, self.colleague)
        self.assertIsNotNone(share_viewer.created_at)

        share_editor = DocumentShare.objects.create(
            document=self.document,
            user=self.editor,
            permission=DocumentShare.Permission.EDITOR,
        )
        self.assertEqual(share_editor.permission, DocumentShare.Permission.EDITOR)

        self.assertEqual(self.document.shares.count(), 2)
        self.assertEqual(self.colleague.document_shares.count(), 1)
        self.assertEqual(self.editor.document_shares.count(), 1)
        self.assertIn('Collaborative Spec', str(share_viewer))

    def test_duplicate_share_prevention_via_model_save(self):
        DocumentShare.objects.create(
            document=self.document,
            user=self.colleague,
            permission=DocumentShare.Permission.VIEWER,
        )
        duplicate_share = DocumentShare(
            document=self.document,
            user=self.colleague,
            permission=DocumentShare.Permission.EDITOR,
        )
        with self.assertRaises(ValidationError):
            duplicate_share.save()

    def test_duplicate_share_prevention_at_database_level(self):
        DocumentShare.objects.create(
            document=self.document,
            user=self.colleague,
        )
        with self.assertRaises(IntegrityError):
            DocumentShare.objects.bulk_create([
                DocumentShare(document=self.document, user=self.colleague)
            ])

    def test_rejection_of_owner_self_sharing(self):
        self_share = DocumentShare(
            document=self.document,
            user=self.owner,
            permission=DocumentShare.Permission.EDITOR,
        )
        with self.assertRaises(ValidationError):
            self_share.clean()

        with self.assertRaises(ValidationError):
            self_share.save()

        self.assertEqual(self.document.shares.count(), 0)


class DocumentFeaturesAndPermissionsTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='password123')
        self.bob = User.objects.create_user(username='bob', password='password123')
        self.charlie = User.objects.create_user(username='charlie', password='password123')

        self.alice_doc = Document.objects.create(
            title="Alice's Secret Strategy",
            content='<p>Top secret plans.</p>',
            owner=self.alice,
        )

    def test_authenticated_user_sees_their_own_documents(self):
        self.client.login(username='alice', password='password123')
        response = self.client.get(reverse('documents:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice&#x27;s Secret Strategy")

        self.client.logout()
        self.client.login(username='bob', password='password123')
        response = self.client.get(reverse('documents:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Alice&#x27;s Secret Strategy")

    def test_shared_documents_appear_in_shared_with_me(self):
        DocumentShare.objects.create(
            document=self.alice_doc,
            user=self.bob,
            permission=DocumentShare.Permission.VIEWER,
        )

        self.client.login(username='bob', password='password123')
        response = self.client.get(reverse('documents:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice&#x27;s Secret Strategy")
        self.assertContains(response, 'Shared by alice')
        self.assertContains(response, 'viewer')

    def test_owner_can_create_document(self):
        self.client.login(username='alice', password='password123')
        response = self.client.post(reverse('documents:create'))
        self.assertEqual(response.status_code, 302)

        created_doc = Document.objects.filter(owner=self.alice).exclude(pk=self.alice_doc.pk).first()
        self.assertIsNotNone(created_doc)
        self.assertEqual(created_doc.title, 'Untitled Document')
        self.assertRedirects(response, reverse('documents:editor', kwargs={'pk': created_doc.pk}))

    def test_owner_can_edit_and_save_title_and_content(self):
        self.client.login(username='alice', password='password123')
        save_url = reverse('documents:autosave', kwargs={'pk': self.alice_doc.pk})

        payload = {
            'title': 'Updated Strategy 2027',
            'content': '<p>New quarterly objectives with <b>bold goals</b>.</p>',
        }
        response = self.client.post(
            save_url,
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'saved')
        self.assertEqual(data['title'], 'Updated Strategy 2027')

        self.alice_doc.refresh_from_db()
        self.assertEqual(self.alice_doc.title, 'Updated Strategy 2027')
        self.assertIn('<b>bold goals</b>', self.alice_doc.content)

    def test_viewer_cannot_edit_or_save(self):
        DocumentShare.objects.create(
            document=self.alice_doc,
            user=self.bob,
            permission=DocumentShare.Permission.VIEWER,
        )

        self.client.login(username='bob', password='password123')

        editor_response = self.client.get(reverse('documents:editor', kwargs={'pk': self.alice_doc.pk}))
        self.assertEqual(editor_response.status_code, 200)
        self.assertContains(editor_response, 'view-only')

        save_url = reverse('documents:autosave', kwargs={'pk': self.alice_doc.pk})
        payload = {'title': 'Hacked Title', 'content': '<p>Hacked content</p>'}
        response = self.client.post(
            save_url,
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

        self.alice_doc.refresh_from_db()
        self.assertNotEqual(self.alice_doc.title, 'Hacked Title')

    def test_editor_share_can_edit_and_save(self):
        DocumentShare.objects.create(
            document=self.alice_doc,
            user=self.charlie,
            permission=DocumentShare.Permission.EDITOR,
        )

        self.client.login(username='charlie', password='password123')
        save_url = reverse('documents:autosave', kwargs={'pk': self.alice_doc.pk})
        payload = {'title': 'Collaborated Strategy', 'content': '<p>Charlie added value.</p>'}
        response = self.client.post(
            save_url,
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        self.alice_doc.refresh_from_db()
        self.assertEqual(self.alice_doc.title, 'Collaborated Strategy')

    def test_unauthenticated_users_cannot_access_protected_routes(self):
        routes = [
            reverse('documents:dashboard'),
            reverse('documents:create'),
            reverse('documents:editor', kwargs={'pk': self.alice_doc.pk}),
            reverse('documents:autosave', kwargs={'pk': self.alice_doc.pk}),
            reverse('documents:delete', kwargs={'pk': self.alice_doc.pk}),
            reverse('documents:import_document'),
        ]
        for route in routes:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 302, f"Failed on route {route}")
            self.assertIn(reverse('login'), response.url)

    def test_user_cannot_access_another_users_private_document(self):
        self.client.login(username='bob', password='password123')

        editor_url = reverse('documents:editor', kwargs={'pk': self.alice_doc.pk})
        response = self.client.get(editor_url)
        self.assertEqual(response.status_code, 404)

        save_url = reverse('documents:autosave', kwargs={'pk': self.alice_doc.pk})
        save_response = self.client.post(
            save_url,
            data=json.dumps({'title': 'Intruder', 'content': 'test'}),
            content_type='application/json',
        )
        self.assertEqual(save_response.status_code, 404)

    def test_owner_can_delete_while_non_owner_cannot(self):
        DocumentShare.objects.create(
            document=self.alice_doc,
            user=self.bob,
            permission=DocumentShare.Permission.EDITOR,
        )

        delete_url = reverse('documents:delete', kwargs={'pk': self.alice_doc.pk})

        self.client.login(username='bob', password='password123')
        response_bob = self.client.post(delete_url)
        self.assertEqual(response_bob.status_code, 403)
        self.assertTrue(Document.objects.filter(pk=self.alice_doc.pk).exists())

        self.client.logout()
        self.client.login(username='charlie', password='password123')
        response_charlie = self.client.post(delete_url)
        self.assertIn(response_charlie.status_code, [403, 404])
        self.assertTrue(Document.objects.filter(pk=self.alice_doc.pk).exists())

        self.client.logout()
        self.client.login(username='alice', password='password123')
        response_alice = self.client.post(delete_url)
        self.assertEqual(response_alice.status_code, 302)
        self.assertRedirects(response_alice, reverse('documents:dashboard'))
        self.assertFalse(Document.objects.filter(pk=self.alice_doc.pk).exists())

    def test_html_sanitizer_removes_xss_and_keeps_safe_formatting(self):
        unsafe_html = (
            '<script>alert("xss")</script>'
            '<p style="color: red; position: fixed;">Safe text with <strong>bold</strong></p>'
            '<img src="bad.jpg" onerror="alert(1)">'
            '<a href="javascript:alert(1)">Bad Link</a>'
            '<a href="https://example.com">Good Link</a>'
        )
        cleaned = sanitize_html(unsafe_html)
        self.assertNotIn('<script>', cleaned)
        self.assertNotIn('onerror', cleaned)
        self.assertNotIn('javascript:', cleaned)
        self.assertNotIn('position: fixed', cleaned)
        self.assertIn('<strong>bold</strong>', cleaned)
        self.assertIn('https://example.com', cleaned)


class DocumentImportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='importer',
            password='password123',
        )
        self.client.login(username='importer', password='password123')

    def test_successful_txt_import(self):
        txt_content = "First paragraph line 1\nLine 2 of paragraph.\n\nSecond paragraph text."
        file = SimpleUploadedFile(
            "Meeting_Notes.txt",
            txt_content.encode('utf-8'),
            content_type="text/plain",
        )
        response = self.client.post(reverse('documents:import_document'), {'file': file})
        self.assertEqual(response.status_code, 302)

        doc = Document.objects.filter(owner=self.user, title="Meeting_Notes").first()
        self.assertIsNotNone(doc)
        self.assertRedirects(response, reverse('documents:editor', kwargs={'pk': doc.pk}))
        self.assertIn('<p>First paragraph line 1<br>Line 2 of paragraph.</p>', doc.content)
        self.assertIn('<p>Second paragraph text.</p>', doc.content)

    def test_successful_markdown_import_with_formatting_preserved(self):
        md_content = (
            "# Release Notes\n\n"
            "Here is **bold text** and *italic emphasis*.\n\n"
            "- First feature\n"
            "- Second feature\n\n"
            "Check [Draftly Docs](https://example.com/docs)."
        )
        file = SimpleUploadedFile(
            "Roadmap.md",
            md_content.encode('utf-8'),
            content_type="text/markdown",
        )
        response = self.client.post(reverse('documents:import_document'), {'file': file})
        self.assertEqual(response.status_code, 302)

        doc = Document.objects.filter(owner=self.user, title="Roadmap").first()
        self.assertIsNotNone(doc)
        self.assertRedirects(response, reverse('documents:editor', kwargs={'pk': doc.pk}))
        self.assertIn('<h1>Release Notes</h1>', doc.content)
        self.assertIn('<strong>bold text</strong>', doc.content)
        self.assertIn('<em>italic emphasis</em>', doc.content)
        self.assertIn('<ul>', doc.content)
        self.assertIn('<li>First feature</li>', doc.content)
        self.assertIn('href="https://example.com/docs"', doc.content)

    def test_unsupported_extension_rejected(self):
        pdf_file = SimpleUploadedFile(
            "document.pdf",
            b"%PDF-1.4 dummy binary content",
            content_type="application/pdf",
        )
        initial_count = Document.objects.count()
        response = self.client.post(reverse('documents:import_document'), {'file': pdf_file})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.count(), initial_count)

    def test_oversized_file_rejected(self):
        oversized_data = b"A" * (2 * 1024 * 1024 + 1024)  # > 2 MB
        large_file = SimpleUploadedFile(
            "huge_file.txt",
            oversized_data,
            content_type="text/plain",
        )
        initial_count = Document.objects.count()
        response = self.client.post(reverse('documents:import_document'), {'file': large_file})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.count(), initial_count)

    def test_invalid_utf8_rejected(self):
        invalid_bytes = b"Hello \xff\xfe World with bad utf-8"
        file = SimpleUploadedFile(
            "corrupted.txt",
            invalid_bytes,
            content_type="text/plain",
        )
        initial_count = Document.objects.count()
        response = self.client.post(reverse('documents:import_document'), {'file': file})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.count(), initial_count)

    def test_empty_file_rejected(self):
        empty_file = SimpleUploadedFile(
            "empty.txt",
            b"",
            content_type="text/plain",
        )
        initial_count = Document.objects.count()
        response = self.client.post(reverse('documents:import_document'), {'file': empty_file})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.count(), initial_count)

    def test_unauthenticated_upload_rejected(self):
        self.client.logout()
        file = SimpleUploadedFile("test.txt", b"Valid content", content_type="text/plain")
        initial_count = Document.objects.count()
        response = self.client.post(reverse('documents:import_document'), {'file': file})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)
        self.assertEqual(Document.objects.count(), initial_count)

    def test_imported_document_belongs_to_uploading_user(self):
        other_user = User.objects.create_user(username='other_user', password='password123')
        file = SimpleUploadedFile("ownership_test.md", b"# Ownership", content_type="text/markdown")
        response = self.client.post(reverse('documents:import_document'), {'file': file})
        self.assertEqual(response.status_code, 302)

        doc = Document.objects.get(title="ownership_test")
        self.assertEqual(doc.owner, self.user)
        self.assertNotEqual(doc.owner, other_user)

    def test_uploaded_malicious_html_does_not_execute_and_is_sanitized(self):
        malicious_md = (
            "# Good Heading\n\n"
            "<script>alert('pwned')</script>\n"
            "<img src='invalid.jpg' onerror='alert(1)'>\n"
            "<a href='javascript:alert(2)'>Click me</a>\n"
            "<iframe src='http://evil.com'></iframe>"
        )
        file = SimpleUploadedFile(
            "security_test.md",
            malicious_md.encode('utf-8'),
            content_type="text/markdown",
        )
        response = self.client.post(reverse('documents:import_document'), {'file': file})
        self.assertEqual(response.status_code, 302)

        doc = Document.objects.get(title="security_test")
        self.assertIn('<h1>Good Heading</h1>', doc.content)
        self.assertNotIn('<script>', doc.content)
        self.assertNotIn('onerror', doc.content)
        self.assertNotIn('javascript:', doc.content)
        self.assertNotIn('<iframe', doc.content)

    def test_import_page_get_request(self):
        response = self.client.get(reverse('documents:import_document'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Import Document')


class AuthenticationAndDashboardTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='tester',
            email='tester@example.com',
            password='testpassword123',
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('documents:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_dashboard_accessible_when_authenticated(self):
        self.client.login(username='tester', password='testpassword123')
        response = self.client.get(reverse('documents:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tester')

    def test_health_check_endpoint(self):
        response = self.client.get(reverse('health_check'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_signup_page_renders(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create your Draftly account')

    def test_signup_creates_user_with_email_and_logs_in(self):
        response = self.client.post(reverse('signup'), {
            'username': 'newuser',
            'email': 'NewUser@Example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertRedirects(response, reverse('documents:dashboard'))
        created = User.objects.get(username='newuser')
        self.assertEqual(created.email, 'newuser@example.com')

    def test_signup_rejects_duplicate_email(self):
        response = self.client.post(reverse('signup'), {
            'username': 'another_user',
            'email': 'TESTER@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='another_user').exists())


class DocumentSharingWorkflowTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='doc_owner',
            email='owner@draftly.test',
            password='password123',
        )
        self.viewer_user = User.objects.create_user(
            username='viewer_colleague',
            email='viewer@draftly.test',
            password='password123',
        )
        self.editor_user = User.objects.create_user(
            username='editor_colleague',
            email='editor@draftly.test',
            password='password123',
        )
        self.outsider = User.objects.create_user(
            username='outsider',
            email='outsider@draftly.test',
            password='password123',
        )
        self.document = Document.objects.create(
            title='Shared Project Plan',
            content='<p>Initial plan</p>',
            owner=self.owner,
        )
        self.share_url = reverse('documents:share', kwargs={'pk': self.document.pk})

    def test_owner_sees_share_modal_but_non_owner_does_not(self):
        DocumentShare.objects.create(
            document=self.document,
            user=self.editor_user,
            permission=DocumentShare.Permission.EDITOR,
        )

        self.client.login(username='doc_owner', password='password123')
        owner_resp = self.client.get(reverse('documents:editor', kwargs={'pk': self.document.pk}))
        self.assertEqual(owner_resp.status_code, 200)
        self.assertContains(owner_resp, 'shareDocumentModal')

        self.client.logout()
        self.client.login(username='editor_colleague', password='password123')
        editor_resp = self.client.get(reverse('documents:editor', kwargs={'pk': self.document.pk}))
        self.assertEqual(editor_resp.status_code, 200)
        self.assertNotContains(editor_resp, 'shareDocumentModal')

    def test_owner_shares_as_viewer_and_editor(self):
        self.client.login(username='doc_owner', password='password123')

        # Share as Viewer (case-insensitive email lookup)
        resp_viewer = self.client.post(
            self.share_url,
            data=json.dumps({'email': 'VIEWER@draftly.test', 'permission': 'viewer'}),
            content_type='application/json',
        )
        self.assertEqual(resp_viewer.status_code, 201)
        data_v = resp_viewer.json()
        self.assertEqual(data_v['status'], 'shared')
        self.assertEqual(data_v['share']['permission'], 'viewer')
        self.assertTrue(
            DocumentShare.objects.filter(
                document=self.document,
                user=self.viewer_user,
                permission=DocumentShare.Permission.VIEWER,
            ).exists()
        )

        # Share as Editor
        resp_editor = self.client.post(
            self.share_url,
            data=json.dumps({'email': 'editor@draftly.test', 'permission': 'editor'}),
            content_type='application/json',
        )
        self.assertEqual(resp_editor.status_code, 201)
        self.assertTrue(
            DocumentShare.objects.filter(
                document=self.document,
                user=self.editor_user,
                permission=DocumentShare.Permission.EDITOR,
            ).exists()
        )

    def test_unknown_email_rejected(self):
        self.client.login(username='doc_owner', password='password123')
        resp = self.client.post(
            self.share_url,
            data=json.dumps({'email': 'nobody@draftly.test', 'permission': 'viewer'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.document.shares.count(), 0)

    def test_invalid_permission_rejected(self):
        self.client.login(username='doc_owner', password='password123')
        resp = self.client.post(
            self.share_url,
            data=json.dumps({'email': 'viewer@draftly.test', 'permission': 'admin'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.document.shares.count(), 0)

    def test_duplicate_sharing_rejected(self):
        DocumentShare.objects.create(
            document=self.document,
            user=self.viewer_user,
            permission=DocumentShare.Permission.VIEWER,
        )
        self.client.login(username='doc_owner', password='password123')
        resp = self.client.post(
            self.share_url,
            data=json.dumps({'email': 'viewer@draftly.test', 'permission': 'editor'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.document.shares.count(), 1)
        self.assertIn('already has access', resp.json()['error'])

    def test_owner_cannot_share_with_themselves(self):
        self.client.login(username='doc_owner', password='password123')
        resp = self.client.post(
            self.share_url,
            data=json.dumps({'email': 'owner@draftly.test', 'permission': 'editor'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.document.shares.count(), 0)

    def test_non_owner_cannot_share_document(self):
        DocumentShare.objects.create(
            document=self.document,
            user=self.editor_user,
            permission=DocumentShare.Permission.EDITOR,
        )
        # Editor cannot share
        self.client.login(username='editor_colleague', password='password123')
        resp_editor = self.client.post(
            self.share_url,
            data=json.dumps({'email': 'outsider@draftly.test', 'permission': 'viewer'}),
            content_type='application/json',
        )
        self.assertEqual(resp_editor.status_code, 403)

        # Outsider cannot share (404 to prevent ID probing)
        self.client.logout()
        self.client.login(username='outsider', password='password123')
        resp_outsider = self.client.post(
            self.share_url,
            data=json.dumps({'email': 'viewer@draftly.test', 'permission': 'viewer'}),
            content_type='application/json',
        )
        self.assertEqual(resp_outsider.status_code, 404)
        self.assertEqual(self.document.shares.count(), 1)

    def test_owner_can_change_collaborator_role(self):
        share = DocumentShare.objects.create(
            document=self.document,
            user=self.viewer_user,
            permission=DocumentShare.Permission.VIEWER,
        )
        update_url = reverse('documents:update_share', kwargs={'pk': self.document.pk, 'share_id': share.pk})

        self.client.login(username='doc_owner', password='password123')
        resp = self.client.post(
            update_url,
            data=json.dumps({'permission': 'editor'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        share.refresh_from_db()
        self.assertEqual(share.permission, DocumentShare.Permission.EDITOR)

    def test_owner_can_revoke_access_and_revoked_user_loses_access(self):
        share = DocumentShare.objects.create(
            document=self.document,
            user=self.editor_user,
            permission=DocumentShare.Permission.EDITOR,
        )
        revoke_url = reverse('documents:revoke_share', kwargs={'pk': self.document.pk, 'share_id': share.pk})

        self.client.login(username='doc_owner', password='password123')
        resp = self.client.post(revoke_url, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(DocumentShare.objects.filter(pk=share.pk).exists())

        # Revoked editor can no longer open or save the document
        self.client.logout()
        self.client.login(username='editor_colleague', password='password123')
        editor_resp = self.client.get(reverse('documents:editor', kwargs={'pk': self.document.pk}))
        self.assertEqual(editor_resp.status_code, 404)

        save_resp = self.client.post(
            reverse('documents:autosave', kwargs={'pk': self.document.pk}),
            data=json.dumps({'title': 'After Revoke', 'content': '<p>Nope</p>'}),
            content_type='application/json',
        )
        self.assertEqual(save_resp.status_code, 404)
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, 'Shared Project Plan')

    def test_viewer_and_editor_cannot_update_roles_or_revoke_access(self):
        viewer_share = DocumentShare.objects.create(
            document=self.document,
            user=self.viewer_user,
            permission=DocumentShare.Permission.VIEWER,
        )
        editor_share = DocumentShare.objects.create(
            document=self.document,
            user=self.editor_user,
            permission=DocumentShare.Permission.EDITOR,
        )
        update_url = reverse('documents:update_share', kwargs={'pk': self.document.pk, 'share_id': viewer_share.pk})
        revoke_url = reverse('documents:revoke_share', kwargs={'pk': self.document.pk, 'share_id': editor_share.pk})

        # Viewer attempts update & revoke -> 403
        self.client.login(username='viewer_colleague', password='password123')
        self.assertEqual(
            self.client.post(update_url, data=json.dumps({'permission': 'editor'}), content_type='application/json').status_code,
            403,
        )
        self.assertEqual(self.client.post(revoke_url, content_type='application/json').status_code, 403)

        # Editor attempts update & revoke -> 403
        self.client.logout()
        self.client.login(username='editor_colleague', password='password123')
        self.assertEqual(
            self.client.post(update_url, data=json.dumps({'permission': 'editor'}), content_type='application/json').status_code,
            403,
        )
        self.assertEqual(self.client.post(revoke_url, content_type='application/json').status_code, 403)

        self.assertEqual(self.document.shares.count(), 2)

    def test_unauthenticated_users_cannot_access_sharing_endpoints(self):
        share = DocumentShare.objects.create(
            document=self.document,
            user=self.viewer_user,
            permission=DocumentShare.Permission.VIEWER,
        )
        endpoints = [
            self.share_url,
            reverse('documents:update_share', kwargs={'pk': self.document.pk, 'share_id': share.pk}),
            reverse('documents:revoke_share', kwargs={'pk': self.document.pk, 'share_id': share.pk}),
        ]
        for url in endpoints:
            resp = self.client.post(url, data=json.dumps({}), content_type='application/json')
            self.assertEqual(resp.status_code, 302)
            self.assertIn(reverse('login'), resp.url)
