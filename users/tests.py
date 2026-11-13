import uuid

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from products.models import Variant
from sales.models import Sale, SaleItem
from .models import Company, User


class RegistrationAndAuthEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_registration_persists_name_and_never_returns_password(self):
        response = self.client.post(
            "/users/register/",
            {
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="ada@example.com")
        self.assertEqual(user.first_name, "Ada")
        self.assertEqual(user.last_name, "Lovelace")
        self.assertTrue(user.check_password("StrongPassword123!"))
        self.assertNotIn("password", response.data["data"])
        self.assertEqual(response.data["data"]["full_name"], "Ada Lovelace")

    def test_invalid_and_duplicate_registration_return_validation_errors(self):
        missing_password = self.client.post(
            "/users/register/",
            {"name": "Ada Lovelace", "email": "ada@example.com"},
            format="json",
        )
        self.assertEqual(missing_password.status_code, 400, missing_password.data)
        self.assertEqual(User.objects.count(), 0)

        valid_data = {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "password": "StrongPassword123!",
        }
        self.assertEqual(self.client.post("/users/register/", valid_data, format="json").status_code, 201)
        duplicate = self.client.post("/users/register/", valid_data, format="json")
        self.assertEqual(duplicate.status_code, 400, duplicate.data)
        self.assertEqual(User.objects.count(), 1)

    def test_login_refresh_company_profile_and_logout(self):
        registered = self.client.post(
            "/users/register/",
            {
                "name": "Grace Hopper",
                "email": "grace@example.com",
                "password": "StrongPassword123!",
            },
            format="json",
        )
        self.assertEqual(registered.status_code, 201, registered.data)

        login = self.client.post(
            "/users/login/",
            {"email": "grace@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        self.assertIn("access", login.data)
        self.assertIn("refresh", login.data)
        self.assertFalse(login.data["has_company"])

        refresh = self.client.post(
            "/users/login/refresh/",
            {"refresh": login.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh.status_code, 200, refresh.data)
        self.assertIn("access", refresh.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.data['access']}")
        company = self.client.post(
            "/users/register/company/",
            {
                "name": "Analytical Engines",
                "email": "contact@example.com",
                "phone": "+2348012345678",
                "location": "London",
            },
            format="multipart",
        )
        self.assertEqual(company.status_code, 201, company.data)

        profile = self.client.get("/users/user/")
        self.assertEqual(profile.status_code, 200, profile.data)
        self.assertEqual(profile.data["user"]["full_name"], "Grace Hopper")
        self.assertNotIn("password", profile.data["user"])

        self.client.cookies["refresh"] = refresh.data.get("refresh", login.data["refresh"])
        logout = self.client.post("/users/logout/", {}, format="json")
        self.assertEqual(logout.status_code, 200, logout.data)


class StoreEndpointWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="StrongPassword123!",
        )
        self.company = Company.objects.create(
            owner=self.user,
            name="Endpoint Test Store",
            location="Lagos",
        )
        self.user.has_company = True
        self.user.save(update_fields=["has_company"])
        access = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_inventory_sales_payment_customer_history_and_receipt_endpoints(self):
        stock = self.client.post(
            "/create/stock/",
            {
                "category": {"name": "Furniture"},
                "products": [
                    {
                        "name": "Chair",
                        "description": "Test chair",
                        "variants": [
                            {
                                "name": "Oak",
                                "color": "oak",
                                "size": "standard",
                                "product_type": "wood",
                                "quantity": 10,
                                "price": "10.00",
                            },
                            {
                                "name": "Walnut",
                                "color": "walnut",
                                "size": "standard",
                                "product_type": "wood",
                                "quantity": 6,
                                "price": "7.00",
                            },
                            {
                                "name": "Pine",
                                "color": "pine",
                                "size": "standard",
                                "product_type": "wood",
                                "quantity": 2,
                                "price": "3.00",
                            },
                        ],
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(stock.status_code, 201, stock.data)
        oak, walnut, pine = stock.data[0]["variants"]

        variant_update = self.client.patch(
            f"/create/edit/{oak['id']}/",
            {"quantity": 11, "price": "12.50"},
            format="json",
        )
        self.assertEqual(variant_update.status_code, 200, variant_update.data)

        variants = self.client.get("/list/variants/")
        self.assertEqual(variants.status_code, 200, variants.data)
        self.assertEqual(len(variants.data), 1)
        variant_detail = self.client.get(f"/list/variants/{oak['id']}/")
        self.assertEqual(variant_detail.status_code, 200, variant_detail.data)
        self.assertEqual(str(variant_detail.data["id"]), str(oak["id"]))

        sale_response = self.client.post(
            "/create/sale/",
            {
                "customer_name": "Test Customer",
                "customer_phone": "+2348098765432",
                "customer_address": "Lagos",
                "seller": "Test Seller",
                "sale_items": [
                    {"variant_id": oak["id"], "quantity": 2, "unit_price": "10.00"}
                ],
            },
            format="json",
        )
        self.assertEqual(sale_response.status_code, 201, sale_response.data)
        sale_id = sale_response.data["id"]
        first_item_id = sale_response.data["sale_items"][0]["id"]

        update_sale = self.client.post(
            "/list/update/",
            {
                "id": sale_id,
                "sale_items": [
                    {"variant_id": walnut["id"], "quantity": 1, "unit_price": "7.00"}
                ],
            },
            format="json",
        )
        self.assertEqual(update_sale.status_code, 200, update_sale.data)
        self.assertEqual(len(update_sale.data["sale_items"]), 2)

        item_patch = self.client.patch(
            f"/list/patch/{first_item_id}/",
            {"quantity": 3, "unit_price": "10.00"},
            format="json",
        )
        self.assertEqual(item_patch.status_code, 200, item_patch.data)

        sale_list = self.client.get("/list/sale/")
        self.assertEqual(sale_list.status_code, 200, sale_list.data)
        self.assertEqual(len(sale_list.data), 1)
        sale_detail = self.client.get(f"/list/sale/{sale_id}/")
        self.assertEqual(sale_detail.status_code, 200, sale_detail.data)

        customers = self.client.get("/list/customer/")
        self.assertEqual(customers.status_code, 200, customers.data)
        customer_id = customers.data[0]["id"]
        customer_detail = self.client.get(f"/list/customer/{customer_id}/")
        self.assertEqual(customer_detail.status_code, 200, customer_detail.data)

        history = self.client.get("/list/history/")
        self.assertEqual(history.status_code, 200, history.data)
        movement_id = history.data[0]["id"]
        history_detail = self.client.get(f"/list/history/{movement_id}/")
        self.assertEqual(history_detail.status_code, 200, history_detail.data)

        unpaid_receipt = self.client.post(
            f"/create/sale/{sale_id}/receipt/",
            {},
            format="json",
            HTTP_X_UUID=str(uuid.uuid4()),
        )
        self.assertEqual(unpaid_receipt.status_code, 200)
        self.assertEqual(unpaid_receipt["Content-Type"], "application/pdf")
        self.assertTrue(unpaid_receipt.content.startswith(b"%PDF"))

        missing_idempotency_key = self.client.post(
            f"/create/sale/{sale_id}/pay/",
            {"amount": "37.00", "method": "cash"},
            format="json",
        )
        self.assertEqual(missing_idempotency_key.status_code, 400, missing_idempotency_key.data)

        idempotency_key = str(uuid.uuid4())
        payment = self.client.post(
            f"/create/sale/{sale_id}/pay/",
            {"amount": "37.00", "method": "cash"},
            format="json",
            HTTP_X_UUID=idempotency_key,
        )
        self.assertEqual(payment.status_code, 200, payment.data)
        repeated_payment = self.client.post(
            f"/create/sale/{sale_id}/pay/",
            {"amount": "37.00", "method": "cash"},
            format="json",
            HTTP_X_UUID=idempotency_key,
        )
        self.assertEqual(repeated_payment.status_code, 200, repeated_payment.data)
        self.assertEqual(repeated_payment.data["id"], payment.data["id"])

        payment_detail = self.client.get(f"/list/payments/{sale_id}/")
        self.assertEqual(payment_detail.status_code, 200, payment_detail.data)
        self.assertEqual(len(payment_detail.data["payments"]), 1)

        receipt = self.client.post(
            f"/create/sale/{sale_id}/receipt/",
            {},
            format="json",
            HTTP_X_UUID=idempotency_key,
        )
        self.assertEqual(receipt.status_code, 200)
        self.assertEqual(receipt["Content-Type"], "application/pdf")
        self.assertTrue(receipt.content.startswith(b"%PDF"))

        sale_items = SaleItem.objects.filter(sale_id=sale_id).order_by("id")
        self.assertEqual(sale_items.count(), 2)
        delete_item = self.client.delete(f"/list/del/{sale_items.last().id}/")
        self.assertEqual(delete_item.status_code, 204)

        delete_variant = self.client.delete(f"/list/variants/{pine['id']}/")
        self.assertEqual(delete_variant.status_code, 204)
        missing_variant = self.client.get(f"/list/variants/{pine['id']}/")
        self.assertEqual(missing_variant.status_code, 404)

    def test_mutating_and_private_endpoints_reject_anonymous_requests(self):
        anonymous_client = APIClient()
        for method, url, data in [
            ("post", "/create/stock/", {}),
            ("post", "/create/sale/", {}),
            ("get", "/list/variants/", None),
            ("get", "/list/sale/", None),
            ("get", "/list/history/", None),
            ("get", "/list/customer/", None),
            ("get", "/users/user/", None),
        ]:
            response = getattr(anonymous_client, method)(url, data or {}, format="json")
            self.assertEqual(response.status_code, 401, f"{method.upper()} {url}: {response.data}")

