import io
import os
import re
import shutil
import sys
import tempfile
import unittest

# Keep test data away from real data: set before the app module is imported.
_BOOT = tempfile.mkdtemp(prefix="vanalaya_boot_")
os.environ["DATA_DIR"] = _BOOT
os.environ["ADMIN_PASSWORD"] = "TestPass123"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

import app as appmod  # noqa: E402


def make_jpeg(size=(2400, 1600), color=(120, 160, 90)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    buf.seek(0)
    return buf


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="vanalaya_test_")
        self.app = appmod.create_app({"DATA_DIR": self.dir, "TESTING": True})
        appmod._hits.clear()
        self.c = self.app.test_client()
        self._conns = []

    def tearDown(self):
        for conn in self._conns:
            conn.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def token(self, client=None):
        client = client or self.c
        client.get("/contact")
        with client.session_transaction() as s:
            return s["csrf"]

    def post(self, url, data=None, client=None, **kw):
        client = client or self.c
        data = dict(data or {})
        data.setdefault("csrf_token", self.token(client))
        return client.post(url, data=data, **kw)

    def login(self, password="TestPass123"):
        return self.post("/admin/login", {"username": "admin", "password": password})

    def db(self):
        import sqlite3
        conn = sqlite3.connect(os.path.join(self.dir, "vanalaya.db"))
        conn.row_factory = sqlite3.Row
        self._conns.append(conn)
        return conn


class PublicPages(Base):
    def test_all_public_pages_load(self):
        for path in ["/", "/about", "/services", "/projects", "/testimonials", "/contact",
                     "/projects?category=eco-friendly", "/projects?q=bamboo",
                     "/robots.txt", "/sitemap.xml"]:
            r = self.c.get(path)
            self.assertEqual(r.status_code, 200, path)

    def test_unknown_page_is_404(self):
        self.assertEqual(self.c.get("/does-not-exist").status_code, 404)
        self.assertEqual(self.c.get("/projects/not-a-project").status_code, 404)

    def test_seed_data_is_in_place(self):
        conn = self.db()
        cats = [r["slug"] for r in conn.execute("SELECT slug FROM categories ORDER BY sort_order")]
        self.assertEqual(cats, ["residential", "commercial", "eco-friendly", "hospitality", "interior-design"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0], 19)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM services").fetchone()[0], 9)

    def test_set_aside_projects_are_not_listed(self):
        body = self.c.get("/projects").get_data(as_text=True)
        self.assertNotIn("Nirmal", body)
        self.assertNotIn("Resort Construction", body)

    def test_no_year_or_status_shown_on_project_page(self):
        body = self.c.get("/projects/basavraj-residence-gokak").get_data(as_text=True)
        self.assertNotIn("Year", body)
        self.assertNotIn("Ongoing", body)

    def test_category_filter_and_search(self):
        body = self.c.get("/projects?category=hospitality").get_data(as_text=True)
        self.assertIn("Bamboo Restaurant, Rastrawadi Nagar", body)
        self.assertNotIn("Basavraj Residence, Gokak</h3>", body)
        body = self.c.get("/projects?q=gokak").get_data(as_text=True)
        self.assertIn("Basavraj Residence", body)
        body = self.c.get("/projects?q=zzzzzz").get_data(as_text=True)
        self.assertIn("No projects match", body)

    def test_contact_details_and_ctas_present(self):
        body = self.c.get("/").get_data(as_text=True)
        self.assertIn("8310347635", body)
        self.assertIn("wa.me/918310347635", body)
        self.assertIn("vanalaya.architecture.studio@gmail.com", body)
        self.assertIn("Get a free consultation", body)
        self.assertIn("Virajpet", body)

    def test_sitemap_lists_projects(self):
        body = self.c.get("/sitemap.xml").get_data(as_text=True)
        self.assertIn("/projects/basavraj-residence-gokak", body)

    def test_seo_basics(self):
        body = self.c.get("/").get_data(as_text=True)
        self.assertIn("<title>", body)
        self.assertIn('name="description"', body)
        self.assertIn("application/ld+json", body)
        self.assertIn("HomeAndConstructionBusiness", body)


class EnquiryForm(Base):
    GOOD = {"name": "Asha", "phone": "9876543210", "email": "asha@example.com",
            "project_type": "Residential", "message": "I want a bamboo house in Coorg."}

    def test_valid_enquiry_is_saved(self):
        r = self.post("/contact", self.GOOD)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/contact/thanks", r.headers["Location"])
        row = self.db().execute("SELECT * FROM enquiries").fetchone()
        self.assertEqual(row["name"], "Asha")
        self.assertEqual(row["status"], "new")
        self.assertEqual(self.c.get("/contact/thanks").status_code, 200)

    def test_missing_fields_show_errors_and_save_nothing(self):
        r = self.post("/contact", {"name": "", "phone": "", "email": "", "message": ""})
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("Please enter your name", body)
        self.assertIn("phone number or an email", body)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM enquiries").fetchone()[0], 0)

    def test_bad_email_and_short_phone_rejected(self):
        bad = dict(self.GOOD, email="not-an-email", phone="123")
        body = self.post("/contact", bad).get_data(as_text=True)
        self.assertIn("email address does not look right", body)
        self.assertIn("phone number looks too short", body)

    def test_honeypot_silently_drops_bots(self):
        r = self.post("/contact", dict(self.GOOD, website="http://spam.example"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM enquiries").fetchone()[0], 0)

    def test_rate_limit_after_five(self):
        for _ in range(5):
            self.assertEqual(self.post("/contact", self.GOOD).status_code, 302)
        body = self.post("/contact", self.GOOD).get_data(as_text=True)
        self.assertIn("several messages recently", body)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM enquiries").fetchone()[0], 5)

    def test_post_without_csrf_token_is_rejected(self):
        r = self.c.post("/contact", data=self.GOOD)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM enquiries").fetchone()[0], 0)

    def test_html_in_message_is_escaped_in_admin(self):
        self.post("/contact", dict(self.GOOD, message="<script>alert(1)</script>"))
        self.login()
        body = self.c.get("/admin/enquiries").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_prefilled_from_project_link(self):
        body = self.c.get("/contact?project=Bamboo+Gate").get_data(as_text=True)
        self.assertIn("Bamboo Gate", body)


class AdminAuth(Base):
    def test_admin_pages_need_login(self):
        for path in ["/admin", "/admin/projects", "/admin/projects/new", "/admin/enquiries",
                     "/admin/services", "/admin/testimonials", "/admin/site", "/admin/password"]:
            r = self.c.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn("/admin/login", r.headers["Location"], path)

    def test_admin_posts_need_login(self):
        for path in ["/admin/projects/1/delete", "/admin/projects/1/toggle/published",
                     "/admin/enquiries/1/delete"]:
            r = self.post(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn("/admin/login", r.headers["Location"], path)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM projects").fetchone()[0], 19)

    def test_wrong_password_rejected(self):
        r = self.login("wrong")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Wrong username or password", r.get_data(as_text=True))
        self.assertEqual(self.c.get("/admin").status_code, 302)

    def test_login_and_logout(self):
        r = self.login()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.c.get("/admin").status_code, 200)
        self.post("/admin/logout")
        self.assertEqual(self.c.get("/admin").status_code, 302)

    def test_login_lockout_after_repeated_failures(self):
        for _ in range(8):
            self.login("bad")
        r = self.login("TestPass123")
        self.assertEqual(r.status_code, 429)

    def test_open_redirect_blocked(self):
        r = self.post("/admin/login?next=https://evil.example", {"username": "admin", "password": "TestPass123"})
        self.assertNotIn("evil.example", r.headers["Location"])

    def test_change_password(self):
        self.login()
        r = self.post("/admin/password", {"current": "TestPass123", "new": "NewPass456", "again": "NewPass456"})
        self.assertEqual(r.status_code, 302)
        self.post("/admin/logout")
        self.assertEqual(self.login("TestPass123").status_code, 200)
        self.assertEqual(self.login("NewPass456").status_code, 302)

    def test_change_password_validation(self):
        self.login()
        body = self.post("/admin/password", {"current": "nope", "new": "NewPass456", "again": "NewPass456"}).get_data(as_text=True)
        self.assertIn("current password is not correct", body)
        body = self.post("/admin/password", {"current": "TestPass123", "new": "short", "again": "short"}).get_data(as_text=True)
        self.assertIn("at least 8 characters", body)
        body = self.post("/admin/password", {"current": "TestPass123", "new": "NewPass456", "again": "Different1"}).get_data(as_text=True)
        self.assertIn("do not match", body)

    def test_security_headers(self):
        r = self.c.get("/")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["X-Frame-Options"], "SAMEORIGIN")


class AdminContent(Base):
    def setUp(self):
        super().setUp()
        self.login()

    def create_project(self, **over):
        data = {"title": "Test Pavilion", "category": "eco-friendly", "location": "Virajpet",
                "summary": "A test pavilion.", "description": "Line one.\n\nLine two.",
                "tags": "bamboo, test", "studio_role": "Design", "published": "1"}
        data.update(over)
        return self.post("/admin/projects/new", data)

    def test_create_edit_and_view_project(self):
        r = self.create_project()
        self.assertEqual(r.status_code, 302)
        row = self.db().execute("SELECT * FROM projects WHERE title='Test Pavilion'").fetchone()
        self.assertEqual(row["slug"], "test-pavilion")
        page = self.c.get("/projects/test-pavilion")
        self.assertEqual(page.status_code, 200)
        self.assertIn("A test pavilion.", page.get_data(as_text=True))
        self.post(f"/admin/projects/{row['id']}", {"title": "Test Pavilion 2", "category": "hospitality",
                                                   "published": "1", "description": "Changed."})
        row = self.db().execute("SELECT * FROM projects WHERE id=?", (row["id"],)).fetchone()
        self.assertEqual(row["title"], "Test Pavilion 2")
        self.assertEqual(row["category"], "hospitality")

    def test_duplicate_titles_get_unique_slugs(self):
        self.create_project()
        self.create_project()
        slugs = [r["slug"] for r in self.db().execute("SELECT slug FROM projects WHERE title='Test Pavilion'")]
        self.assertEqual(sorted(slugs), ["test-pavilion", "test-pavilion-2"])

    def test_project_validation(self):
        body = self.create_project(title="", category="bogus").get_data(as_text=True)
        self.assertIn("Please enter a project title", body)
        self.assertIn("Please choose a category", body)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM projects").fetchone()[0], 19)

    def test_hidden_project_not_public_but_visible_in_admin(self):
        self.create_project(published="")
        self.assertEqual(self.c.get("/projects/test-pavilion").status_code, 404)
        self.assertNotIn("Test Pavilion", self.c.get("/projects").get_data(as_text=True))
        self.assertIn("Test Pavilion", self.c.get("/admin/projects").get_data(as_text=True))
        self.assertNotIn("test-pavilion", self.c.get("/sitemap.xml").get_data(as_text=True))

    def test_toggle_published_and_featured(self):
        pid = self.db().execute("SELECT id FROM projects WHERE slug='bamboo-gate-forest-garden-gadchiroli'").fetchone()["id"]
        self.post(f"/admin/projects/{pid}/toggle/published")
        self.assertEqual(self.c.get("/projects/bamboo-gate-forest-garden-gadchiroli").status_code, 404)
        self.post(f"/admin/projects/{pid}/toggle/featured")
        self.assertEqual(self.db().execute("SELECT featured FROM projects WHERE id=?", (pid,)).fetchone()[0], 1)
        self.assertEqual(self.post(f"/admin/projects/{pid}/toggle/bogus").status_code, 404)

    def test_reorder_projects(self):
        first = self.db().execute("SELECT id FROM projects ORDER BY sort_order, id LIMIT 1").fetchone()["id"]
        self.post(f"/admin/projects/{first}/move/down")
        ids = [r["id"] for r in self.db().execute("SELECT id FROM projects ORDER BY sort_order, id")]
        self.assertEqual(ids.index(first), 1)

    def test_photo_upload_resize_cover_and_delete(self):
        self.create_project()
        pid = self.db().execute("SELECT id FROM projects WHERE slug='test-pavilion'").fetchone()["id"]
        r = self.post(f"/admin/projects/{pid}/photos",
                      {"photos": [(make_jpeg(), "one.jpg"), (make_jpeg(color=(10, 90, 40)), "two.jpg")]},
                      content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        imgs = self.db().execute("SELECT * FROM project_images WHERE project_id=? ORDER BY id", (pid,)).fetchall()
        self.assertEqual(len(imgs), 2)
        self.assertEqual([i["is_cover"] for i in imgs], [1, 0])
        up = os.path.join(self.dir, "uploads")
        big = Image.open(os.path.join(up, imgs[0]["filename"] + ".jpg"))
        small = Image.open(os.path.join(up, imgs[0]["filename"] + "_t.jpg"))
        self.assertLessEqual(max(big.size), 1800)
        self.assertLessEqual(max(small.size), 700)
        self.assertEqual(self.c.get(f"/media/{imgs[0]['filename']}_t.jpg").status_code, 200)
        page = self.c.get("/projects/test-pavilion").get_data(as_text=True)
        self.assertIn(imgs[0]["filename"], page)
        self.assertIn(imgs[0]["filename"] + "_t.jpg", self.c.get("/projects").get_data(as_text=True))

        self.post(f"/admin/photos/{imgs[1]['id']}/cover")
        covers = [r["is_cover"] for r in self.db().execute("SELECT is_cover FROM project_images WHERE project_id=? ORDER BY id", (pid,))]
        self.assertEqual(covers, [0, 1])
        self.post(f"/admin/photos/{imgs[1]['id']}/caption", {"caption": "Front view"})
        self.assertIn("Front view", self.c.get("/projects/test-pavilion").get_data(as_text=True))

        self.post(f"/admin/photos/{imgs[1]['id']}/delete")
        left = self.db().execute("SELECT * FROM project_images WHERE project_id=?", (pid,)).fetchall()
        self.assertEqual(len(left), 1)
        self.assertEqual(left[0]["is_cover"], 1)
        self.assertFalse(os.path.exists(os.path.join(up, imgs[1]["filename"] + ".jpg")))

    def test_non_image_upload_rejected(self):
        self.create_project()
        pid = self.db().execute("SELECT id FROM projects WHERE slug='test-pavilion'").fetchone()["id"]
        r = self.post(f"/admin/projects/{pid}/photos",
                      {"photos": [(io.BytesIO(b"<?php echo 1;"), "evil.php"),
                                  (io.BytesIO(b"not really an image"), "fake.jpg")]},
                      content_type="multipart/form-data", follow_redirects=True)
        self.assertIn("were skipped", r.get_data(as_text=True))
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM project_images").fetchone()[0], 0)
        self.assertEqual(os.listdir(os.path.join(self.dir, "uploads")), [])

    def test_delete_project_removes_photos(self):
        self.create_project()
        pid = self.db().execute("SELECT id FROM projects WHERE slug='test-pavilion'").fetchone()["id"]
        self.post(f"/admin/projects/{pid}/photos", {"photos": [(make_jpeg(), "a.jpg")]},
                  content_type="multipart/form-data")
        self.assertGreater(len(os.listdir(os.path.join(self.dir, "uploads"))), 0)
        self.post(f"/admin/projects/{pid}/delete")
        self.assertEqual(self.c.get("/projects/test-pavilion").status_code, 404)
        self.assertEqual(os.listdir(os.path.join(self.dir, "uploads")), [])
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM project_images").fetchone()[0], 0)

    def test_video_link_validation_and_embed(self):
        body = self.create_project(title="Bad Video", video_url="javascript:alert(1)").get_data(as_text=True)
        self.assertIn("must start with http", body)
        self.create_project(title="Good Video", video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        page = self.c.get("/projects/good-video").get_data(as_text=True)
        self.assertIn("youtube.com/embed/dQw4w9WgXcQ", page)

    def test_enquiry_status_note_and_delete(self):
        self.post("/contact", EnquiryForm.GOOD)
        eid = self.db().execute("SELECT id FROM enquiries").fetchone()["id"]
        self.assertIn("Asha", self.c.get("/admin/enquiries").get_data(as_text=True))
        self.post(f"/admin/enquiries/{eid}", {"status": "contacted", "private_note": "Called on Monday"})
        row = self.db().execute("SELECT * FROM enquiries WHERE id=?", (eid,)).fetchone()
        self.assertEqual((row["status"], row["private_note"]), ("contacted", "Called on Monday"))
        self.assertNotIn("Asha", self.c.get("/admin/enquiries?status=new").get_data(as_text=True))
        self.post(f"/admin/enquiries/{eid}/delete")
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM enquiries").fetchone()[0], 0)

    def test_services_add_edit_delete(self):
        self.post("/admin/services", {"action": "add", "title": "Pool Design", "description": "Pools."})
        self.assertIn("Pool Design", self.c.get("/services").get_data(as_text=True))
        sid = self.db().execute("SELECT id FROM services WHERE title='Pool Design'").fetchone()["id"]
        self.post("/admin/services", {"action": "save", "id": sid, "title": "Pool and Pond Design", "description": "More."})
        self.assertIn("Pool and Pond Design", self.c.get("/services").get_data(as_text=True))
        self.post("/admin/services", {"action": "delete", "id": sid})
        self.assertNotIn("Pool and Pond Design", self.c.get("/services").get_data(as_text=True))

    def test_testimonials_flow(self):
        self.assertIn("will appear here soon", self.c.get("/testimonials").get_data(as_text=True))
        self.post("/admin/testimonials", {"action": "add", "client_name": "R. Gowda",
                                          "project_name": "Farm house", "quote": "Beautiful bamboo work."})
        self.assertIn("Beautiful bamboo work.", self.c.get("/testimonials").get_data(as_text=True))
        self.assertIn("Beautiful bamboo work.", self.c.get("/").get_data(as_text=True))
        tid = self.db().execute("SELECT id FROM testimonials").fetchone()["id"]
        self.post("/admin/testimonials", {"action": "save", "id": tid, "client_name": "R. Gowda",
                                          "project_name": "Farm house", "quote": "Beautiful bamboo work."})
        self.assertNotIn("Beautiful bamboo work.", self.c.get("/testimonials").get_data(as_text=True))
        self.post("/admin/testimonials", {"action": "delete", "id": tid})
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM testimonials").fetchone()[0], 0)

    def test_site_text_editing(self):
        self.post("/admin/site", {"hero_headline": "A brand new headline", "phone": "9000000000",
                                  "whatsapp": "+91 90000 00000", "email": "x@example.com",
                                  "address": "Coorg", "instagram": "newhandle", "about_text": "New about.",
                                  "about_title": "T", "hero_sub": "S", "cta_text": "Book a call",
                                  "founder_name": "F", "founder_role": "R", "founder_text": "T",
                                  "eco_title": "E", "eco_text": "E"})
        home = self.c.get("/").get_data(as_text=True)
        self.assertIn("A brand new headline", home)
        self.assertIn("wa.me/919000000000", home)
        self.assertIn("Book a call", home)
        self.assertIn("newhandle", home)

    def test_dashboard_counts(self):
        self.post("/contact", EnquiryForm.GOOD)
        body = self.c.get("/admin").get_data(as_text=True)
        self.assertIn("new enquiries", body)
        self.assertIn("projects without photos", body)


class FirstRun(unittest.TestCase):
    def test_generated_admin_password_file_when_none_set(self):
        d = tempfile.mkdtemp(prefix="vanalaya_first_")
        old = os.environ.pop("ADMIN_PASSWORD")
        try:
            appmod.create_app({"DATA_DIR": d, "TESTING": True})
            with open(os.path.join(d, "first_admin_login.txt")) as fh:
                text = fh.read()
            self.assertIn("username: admin", text)
            pw = re.search(r"password: (\S+)", text).group(1)
            self.assertGreaterEqual(len(pw), 10)
        finally:
            os.environ["ADMIN_PASSWORD"] = old
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
