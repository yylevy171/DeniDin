"""Feature 066: the document JSON exposes a payment's app type and cheque number."""
from denidin_mcp_morning.models import Payment


def test_cheque_number_and_app_type_are_read_from_morning_shape():
    cheque = Payment.model_validate({"price": 5, "amount": 5, "type": 2, "chequeNum": 987654})
    assert cheque.cheque_number == "987654" and cheque.app_type is None
    bit = Payment.model_validate({"amount": 5, "type": 10, "appType": 1})
    assert bit.app_type == 1 and bit.cheque_number is None
