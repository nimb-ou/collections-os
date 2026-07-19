"""
Payments Page (Dev Flow)
Mark accounts as paid for development/testing
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from decimal import Decimal

from database import execute_query, execute_insert_returning
from auth import require_permission, get_current_user


@require_permission("payments")
def render():
    """Render Payments page."""
    st.title("💰 Payments (Dev)")
    st.markdown(f"**Date:** {date.today().strftime('%Y-%m-%d')}")
    st.markdown("---")

    st.warning("""
    **Development Mode**

    This page allows manual payment entry for development and testing.
    In production, payments would be imported from the bank's payment system.
    """)

    # Tabs
    tab1, tab2 = st.tabs(["Mark Payment", "Recent Payments"])

    with tab1:
        show_mark_payment_form()

    with tab2:
        show_recent_payments()


def show_mark_payment_form():
    """Display form to mark account as paid."""
    st.subheader("Mark Account as Paid")

    with st.form("mark_payment_form"):
        col1, col2 = st.columns(2)

        with col1:
            account_id = st.text_input(
                "Account ID*",
                help="Enter the account ID to mark as paid"
            )

            # Lookup account details
            if account_id:
                try:
                    query = """
                        SELECT
                            a.account_id,
                            c.name as customer_name,
                            mad.overdue_amt,
                            mad.bucket,
                            mad.dpd
                        FROM dim_account a
                        JOIN dim_customer c ON a.customer_id = c.customer_id
                        LEFT JOIN mart_account_daily mad ON a.account_id = mad.account_id
                            AND mad.date = CURRENT_DATE
                        WHERE a.account_id = %s
                    """
                    results = execute_query(query, (account_id,))

                    if results:
                        acc = results[0]
                        st.info(f"""
                        **Account Details:**
                        - Customer: {acc['customer_name']}
                        - Bucket: {acc['bucket'] or 'N/A'}
                        - DPD: {acc['dpd'] or 0} days
                        - Overdue: ₹{(acc['overdue_amt'] or 0)/100000:.2f}L
                        """)
                    else:
                        st.warning("Account not found")

                except Exception as e:
                    st.error(f"Error looking up account: {e}")

            amount = st.number_input(
                "Payment Amount*",
                min_value=0.0,
                step=1000.0,
                help="Amount received in ₹"
            )

            pay_mode = st.selectbox(
                "Payment Mode*",
                options=["UPI", "NEFT", "CASH", "CHEQUE", "ONLINE", "POS"],
                help="How was payment received?"
            )

        with col2:
            pay_date = st.date_input(
                "Payment Date*",
                value=date.today(),
                help="Date of payment"
            )

            reference = st.text_input(
                "Reference/Transaction ID",
                help="Bank reference number (optional)"
            )

            notes = st.text_area(
                "Notes",
                help="Additional notes (optional)"
            )

        submitted = st.form_submit_button("Record Payment", use_container_width=True)

        if submitted:
            if not account_id or amount <= 0 or not pay_mode:
                st.error("Please fill all required fields")
            else:
                record_payment(account_id, amount, pay_mode, pay_date, reference, notes)


def record_payment(account_id: str, amount: float, pay_mode: str, pay_date: date,
                   reference: str = None, notes: str = None):
    """
    Record a payment in the system.

    Args:
        account_id: Account identifier
        amount: Payment amount
        pay_mode: Payment mode
        pay_date: Payment date
        reference: Reference number
        notes: Additional notes
    """
    try:
        user = get_current_user()

        # Insert payment
        query = """
            INSERT INTO fct_payments (
                account_id, pay_date, amount, pay_mode,
                reference, notes, created_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s
            ) RETURNING payment_id
        """

        result = execute_insert_returning(
            query,
            (account_id, pay_date, amount, pay_mode, reference, notes, user['user_id'])
        )

        if result:
            st.success(f"✅ Payment recorded successfully! Payment ID: {result['payment_id']}")
            st.balloons()
            st.info("""
            **Next Steps:**
            1. Run `make daily` to refresh marts and reflect this payment
            2. The account's overdue amount and bucket will update accordingly
            3. Payment will appear in dashboards after mart refresh
            """)
        else:
            st.error("Failed to record payment")

    except Exception as e:
        st.error(f"Error recording payment: {e}")


def show_recent_payments():
    """Display recent payments."""
    st.subheader("Recent Payments (Last 7 Days)")

    try:
        query = """
            SELECT
                fp.payment_id,
                fp.account_id,
                dc.name as customer_name,
                fp.amount,
                fp.pay_mode,
                fp.pay_date,
                fp.reference,
                u.username as created_by,
                fp.created_at
            FROM fct_payments fp
            JOIN dim_account da ON fp.account_id = da.account_id
            JOIN dim_customer dc ON da.customer_id = dc.customer_id
            LEFT JOIN users u ON fp.created_by = u.user_id
            WHERE fp.pay_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY fp.created_at DESC
            LIMIT 100
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
            df['amount_l'] = (df['amount'] / 100000).round(2)

            st.dataframe(
                df[['payment_id', 'account_id', 'customer_name', 'amount_l', 'pay_mode',
                    'pay_date', 'reference', 'created_by', 'created_at']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    'amount_l': 'Amount (L)',
                    'pay_mode': 'Mode',
                    'pay_date': 'Pay Date',
                    'created_at': 'Recorded At'
                }
            )

            # Summary
            total_amount = df['amount'].sum()
            total_count = len(df)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Payments (7d)", f"{total_count:,}")
            with col2:
                st.metric("Total Amount (7d)", f"₹{total_amount/100000:.2f}L")

        else:
            st.info("No recent payments")

    except Exception as e:
        st.error(f"Error loading recent payments: {e}")
