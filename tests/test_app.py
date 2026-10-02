import unittest

import app as rain_app


class CalculationTests(unittest.TestCase):
    def test_yield_uses_one_runoff_factor_and_one_collection_efficiency(self):
        result = rain_app.calculate_water(650, 100, "Other")
        self.assertEqual(result["water"], 38675)
        self.assertEqual(result["water_m3"], 38.675)
        self.assertEqual(result["coefficient"], 0.70)
        self.assertEqual(result["efficiency"], 0.85)

    def test_each_supported_roof_type_uses_its_configured_coefficient(self):
        for roof_type, coefficient in rain_app.ROOF_COEFFICIENTS.items():
            with self.subTest(roof_type=roof_type):
                result = rain_app.calculate_water(1000, 10, roof_type)
                self.assertEqual(result["water"], 10 * 1000 * coefficient * 0.85)
                self.assertEqual(result["water_m3"], result["water"] / 1000)
                self.assertEqual(result["efficiency"], 0.85)

    def test_area_unit_conversion_preserves_physical_area(self):
        common = {
            "state": "Punjab",
            "district": "Amritsar",
            "water_unit": "litres",
            "roof_type": "RCC / Concrete",
        }
        metric = rain_app.process_calculator_form(
            {**common, "roof_area": "100", "area_unit": "m2"}
        )
        imperial = rain_app.process_calculator_form(
            {**common, "roof_area": str(100 / 0.092903), "area_unit": "ft2"}
        )
        self.assertIsNone(metric["error_message"])
        self.assertIsNone(imperial["error_message"])
        self.assertAlmostEqual(metric["result"]["area"], imperial["result"]["area"])
        self.assertAlmostEqual(metric["result"]["water"], imperial["result"]["water"])

    def test_missing_invalid_nonpositive_and_oversized_areas_are_rejected(self):
        common = {
            "state": "Punjab",
            "district": "Amritsar",
            "area_unit": "m2",
            "water_unit": "litres",
            "roof_type": "RCC / Concrete",
        }
        for area in ("", "not-a-number", "nan", "inf", "0", "-1", "100000.01"):
            with self.subTest(area=area):
                result = rain_app.process_calculator_form(
                    {**common, "roof_area": area}
                )
                self.assertIsNotNone(result["error_message"])
                self.assertIsNone(result["result"])

    def test_maximum_area_is_applied_after_square_foot_conversion(self):
        result = rain_app.process_calculator_form(
            {
                "state": "Punjab",
                "district": "Amritsar",
                "roof_area": str(100000 / 0.092903),
                "area_unit": "ft2",
                "water_unit": "m3",
                "roof_type": "Metal Sheet",
            }
        )
        self.assertIsNone(result["error_message"])
        self.assertAlmostEqual(result["result"]["area"], 100000)

    def test_maximum_square_metre_area_is_valid_and_area_limit_is_enforced(self):
        form = {
            "state": "Punjab",
            "district": "Amritsar",
            "roof_area": "100000",
            "area_unit": "m2",
            "water_unit": "litres",
            "roof_type": "RCC / Concrete",
        }
        at_limit = rain_app.process_calculator_form(form)
        over_limit = rain_app.process_calculator_form({**form, "roof_area": "100000.0001"})
        self.assertIsNone(at_limit["error_message"])
        self.assertEqual(at_limit["result"]["area"], rain_app.MAX_ROOF_AREA_M2)
        self.assertEqual(at_limit["result"]["water"], 100000 * 680 * 0.80 * 0.85)
        self.assertEqual(over_limit["error_message"], "Roof area exceeds the supported maximum of 100,000 m².")
        self.assertIsNone(over_limit["result"])

    def test_area_and_water_units_produce_equivalent_estimates(self):
        base = {
            "state": "Punjab",
            "district": "Amritsar",
            "roof_type": "Tiles",
        }
        metric = rain_app.process_calculator_form(
            {**base, "roof_area": "100", "area_unit": "m2", "water_unit": "litres"}
        )
        imperial = rain_app.process_calculator_form(
            {
                **base,
                "roof_area": str(100 / 0.092903),
                "area_unit": "ft2",
                "water_unit": "m3",
            }
        )
        self.assertAlmostEqual(metric["result"]["water"], imperial["result"]["water"])
        self.assertAlmostEqual(
            imperial["result"]["water_m3"],
            metric["result"]["water"] / 1000,
        )

    def test_unknown_localities_and_unsupported_units_are_rejected(self):
        base = {
            "state": "Punjab",
            "district": "Not a district",
            "roof_area": "100",
            "area_unit": "m2",
            "water_unit": "litres",
            "roof_type": "RCC / Concrete",
        }
        self.assertIsNotNone(rain_app.process_calculator_form(base)["error_message"])
        invalid_area_unit = rain_app.process_calculator_form(
            {**base, "district": "Amritsar", "area_unit": "yards"}
        )
        invalid_water_unit = rain_app.process_calculator_form(
            {**base, "district": "Amritsar", "water_unit": "gallons"}
        )
        self.assertIsNotNone(invalid_area_unit["error_message"])
        self.assertIsNotNone(invalid_water_unit["error_message"])

    def test_unknown_roof_type_is_not_silently_defaulted(self):
        with self.assertRaises(ValueError):
            rain_app.calculate_water(650, 100, "Unknown roof")

    def test_all_rainfall_overrides_reference_real_district_options(self):
        for state, overrides in rain_app.RAINFALL_OVERRIDES.items():
            for district in overrides:
                with self.subTest(state=state, district=district):
                    self.assertIn(district, rain_app.DISTRICTS[state])

    def test_invalid_district_does_not_fall_back_to_state_rainfall(self):
        self.assertEqual(rain_app.get_locality_values("Punjab", "Not a district"), ("", 0))
        self.assertEqual(
            rain_app.get_locality_values("Punjab", "Amritsar"),
            ("Amritsar", 680),
        )


class RouteTests(unittest.TestCase):
    def setUp(self):
        rain_app.app.config.update(TESTING=True)
        self.client = rain_app.app.test_client()

    def test_existing_routes_render(self):
        for path in ("/", "/calculator", "/about", "/benefits"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_home_and_calculator_share_calculation_behavior(self):
        form = {
            "state": "Punjab",
            "district": "Amritsar",
            "roof_area": "100",
            "area_unit": "m2",
            "water_unit": "litres",
            "roof_type": "Other",
        }
        for path in ("/", "/calculator"):
            with self.subTest(path=path):
                response = self.client.post(path, data=form)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"40,460", response.data)
                self.assertIn(b"680 mm/year", response.data)

    def test_invalid_post_renders_an_inline_error(self):
        response = self.client.post(
            "/calculator",
            data={
                "state": "Punjab",
                "district": "Amritsar",
                "roof_area": "",
                "area_unit": "m2",
                "water_unit": "litres",
                "roof_type": "RCC / Concrete",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Enter your roof area", response.data)

    def test_calculator_renders_result_in_requested_water_unit(self):
        response = self.client.post(
            "/calculator",
            data={
                "state": "Punjab",
                "district": "Amritsar",
                "roof_area": "100",
                "area_unit": "m2",
                "water_unit": "m3",
                "roof_type": "Other",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"40.46", response.data)
        self.assertIn(b"CUBIC METRES / YEAR", response.data)
        self.assertIn(b"COLLECTION EFFICIENCY", response.data)
        self.assertIn(b"85%", response.data)

    def test_invalid_area_values_render_errors_in_both_calculators(self):
        base = {
            "state": "Punjab",
            "district": "Amritsar",
            "area_unit": "m2",
            "water_unit": "litres",
            "roof_type": "Other",
        }
        for path in ("/", "/calculator"):
            for area in ("", "not-a-number", "0", "-1", "100000.01"):
                with self.subTest(path=path, area=area):
                    response = self.client.post(path, data={**base, "roof_area": area})
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(b"role=\"alert\"", response.data)
                    self.assertNotIn(b"Estimated annual harvestable water using", response.data)


if __name__ == "__main__":
    unittest.main()
