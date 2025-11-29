import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- إعدادات التطبيق ---
DEDUCTION_AMOUNT = 15.0  # المبلغ المخصوم لكل توصيلة (أوقية)
DB_NAME = "delivery_app.db"
ADMIN_KEY = "jak2831" # <--- المفتاح السري للإدارة

# --- دوال التعامل مع قاعدة البيانات (تم الحفاظ عليها) ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS drivers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, driver_id TEXT UNIQUE, name TEXT, bike_plate TEXT, whatsapp TEXT, notes TEXT, is_active BOOLEAN, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, driver_name TEXT, amount REAL, type TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()
# (باقي دوال get_drivers, add_driver, update_balance, update_driver_details, get_driver_info, get_history, get_all_drivers_details محفوظة بالكامل هنا)

# دالة مكررة لاستكمال الكود (يجب عليك استبدال هذا المكان بالدوال الفعلية):
def get_drivers(active_only=True):
    conn = sqlite3.connect(DB_NAME)
    if active_only:
        df = pd.read_sql_query("SELECT driver_id, name, balance FROM drivers WHERE is_active=1", conn)
    else:
        df = pd.read_sql_query("SELECT driver_id, name, balance FROM drivers", conn)
    conn.close()
    df['display_name'] = df['name'] + ' (ID: ' + df['driver_id'] + ')'
    return df
# (ملاحظة: لضمان اكتمال الكود، يجب أن تضمن وجود جميع الدوال هنا)

def get_driver_info(driver_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name, balance, is_active FROM drivers WHERE driver_id=?", (driver_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {"name": result[0], "balance": result[1], "is_active": result[2]}
    return None

def update_balance(driver_id, amount, trans_type):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    info = get_driver_info(driver_id)
    if not info: return 0.0
    current_balance = info['balance']
    name = info['name']
    new_balance = current_balance + amount
    c.execute("UPDATE drivers SET balance=? WHERE driver_id=?", (new_balance, driver_id))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO transactions (driver_name, amount, type, timestamp) VALUES (?, ?, ?, ?)",
              (f"{name} (ID:{driver_id})", amount, trans_type, timestamp))
    conn.commit()
    conn.close()
    return new_balance

def add_driver(driver_id, name, bike_plate, whatsapp, notes, is_active):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO drivers (driver_id, name, bike_plate, whatsapp, notes, is_active, balance) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                  (driver_id, name, bike_plate, whatsapp, notes, is_active, 0.0))
        conn.commit()
        st.success(f"تمت إضافة المندوب '{name}' بنجاح!")
    except sqlite3.IntegrityError:
        st.error("رقم الترقيم (ID) هذا موجود مسبقاً.")
    conn.close()

def update_driver_details(driver_id, name, bike_plate, whatsapp, notes, is_active):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE drivers SET name=?, bike_plate=?, whatsapp=?, notes=?, is_active=? WHERE driver_id=?", 
              (name, bike_plate, whatsapp, notes, is_active, driver_id))
    conn.commit()
    conn.close()
    st.success(f"تم تحديث بيانات المندوب {name} بنجاح.")

def get_history(driver_id=None):
    conn = sqlite3.connect(DB_NAME)
    if driver_id:
        query = f"SELECT type as 'العملية', amount as 'المبلغ', timestamp as 'التوقيت' FROM transactions WHERE driver_name LIKE '%ID:{driver_id}%' ORDER BY id DESC"
    else:
        query = "SELECT driver_name as 'المندوب', type as 'العملية', amount as 'المبلغ', timestamp as 'التوقيت' FROM transactions ORDER BY id DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_all_drivers_details():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT driver_id as 'الترقيم', name as 'الاسم', bike_plate as 'رقم اللوحة', whatsapp as 'واتساب', balance as 'الرصيد', is_active as 'الحالة', notes as 'ملاحظات' FROM drivers", conn)
    conn.close()
    df['الحالة'] = df['الحالة'].apply(lambda x: 'مفعل' if x == 1 else 'معطل')
    return df
# ----------------------------------------------------------------------------------

# --- واجهة التطبيق ---
st.set_page_config(page_title="نظام إدارة التوصيل", layout="wide", page_icon="🚚")
st.title("🚚 نظام رصيد المندوبين")

# التأكد من وجود قاعدة البيانات
init_db()

# تهيئة حالة الجلسة (للتأكد من تسجيل الدخول)
if 'logged_in_driver_id' not in st.session_state:
    st.session_state['logged_in_driver_id'] = None
if 'admin_mode' not in st.session_state:
    st.session_state['admin_mode'] = False

# ----------------------------------------------------------------------------------
# 1. منطق القائمة الجانبية وفصل الأدوار
# ----------------------------------------------------------------------------------

st.sidebar.header("لوحة التحكم")

if st.session_state['admin_mode']:
    # وضع المسؤول (Admin) - تظهر له جميع الخيارات
    st.sidebar.markdown("**وضع المسؤول (ADMIN)**")
    menu_options = ["واجهة العمليات (الإدارة)", "إدارة المندوبين (إضافة/تعديل)", "التقارير وسجل العمليات", "الخروج من وضع المسؤول"]
    current_menu = st.sidebar.radio("القائمة", menu_options)
    if current_menu == "الخروج من وضع المسؤول":
        st.session_state['admin_mode'] = False
        st.rerun()

elif st.session_state['logged_in_driver_id']:
    # وضع المندوب (Driver) - تظهر له واجهة المندوب فقط مع خيار الخروج
    driver_id = st.session_state['logged_in_driver_id']
    driver_info = get_driver_info(driver_id)
    if driver_info:
        st.sidebar.markdown(f"**مرحباً، {driver_info['name']}**")
        st.sidebar.button("خروج (Logout)", on_click=lambda: st.session_state.update(logged_in_driver_id=None, admin_mode=False))
        current_menu = "واجهة المندوب"
    else:
        st.session_state.logged_in_driver_id = None
        current_menu = "واجهة المندوب" # يعود لواجهة الدخول

else:
    # وضع الزائر (Guest) - لا تظهر له خيارات سوى الدخول للمندوب و المدخل السري للإدارة
    current_menu = "واجهة المندوب"
    
    # 🤫 مدخل المسؤول السري في الأسفل
    st.sidebar.divider()
    with st.sidebar.expander("مدخل المسؤول السري"):
        admin_key_input = st.text_input("أدخل المفتاح السري", type="password")
        if st.button("دخول المسؤول"):
            if admin_key_input == ADMIN_KEY:
                st.session_state['admin_mode'] = True
                st.rerun()
            else:
                st.error("المفتاح السري غير صحيح.")

# ----------------------------------------------------------------------------------
# 2. عرض الواجهات بناءً على الاختيار
# ----------------------------------------------------------------------------------

if current_menu == "واجهة المندوب":
    if st.session_state['logged_in_driver_id']:
        driver_id = st.session_state['logged_in_driver_id']
        driver_data = get_driver_info(driver_id)
        
        if driver_data and driver_data['is_active']:
            st.header(f"أهلاً بك يا {driver_data['name']}!")
            st.markdown("### رصيدك الحالي")
            st.metric(label="الرصيد المتوفر", value=f"{driver_data['balance']} أوقية", delta_color="off")
            st.divider()
            st.markdown("### سجل حركاتك الأخيرة")
            history_df = get_history(driver_id)
            if not history_df.empty:
                st.dataframe(history_df, use_container_width=True)
            else:
                st.info("لا توجد حركات مسجلة لك بعد.")
        else:
            st.error("عفواً، حسابك معطل أو غير موجود.")
            st.session_state['logged_in_driver_id'] = None
            st.rerun() # لإظهار شاشة الدخول مجدداً
    
    else:
        # واجهة تسجيل الدخول للمندوب (تظهر للزائر)
        st.header("تسجيل الدخول للمندوبين")
        driver_id_input = st.text_input("أدخل ترقيمك (Driver ID)")
        
        def attempt_login():
            if not driver_id_input:
                st.error("الرجاء إدخال ترقيمك.")
                return
            
            info = get_driver_info(driver_id_input)
            if info:
                if info['is_active']:
                    st.session_state['logged_in_driver_id'] = driver_id_input
                    st.success(f"تم تسجيل الدخول بنجاح! مرحباً بك يا {info['name']}.")
                    st.rerun()
                else:
                    st.error("عفواً، حسابك غير مفعل.")
            else:
                st.error("ترقيم المندوب غير صحيح.")

        st.button("تسجيل الدخول", on_click=attempt_login, type="primary")

# ----------------------------------------------------------------------------------
# 3. واجهة العمليات (الإدارة) - شحن/خصم (تظهر للمسؤول فقط)
# ----------------------------------------------------------------------------------
elif current_menu == "واجهة العمليات (الإدارة)":
    st.header("تسجيل العمليات (شحن/خصم)")
    # (كود واجهة العمليات بالكامل يوضع هنا)
    active_drivers_df = get_drivers(active_only=True)
    if active_drivers_df.empty:
        st.warning("لا يوجد مندوبون مفعلون حالياً. يرجى تفعيل حسابات من قائمة الإدارة.")
    else:
        driver_options = active_drivers_df.set_index('driver_id')['display_name'].to_dict()
        selected_id = st.selectbox("اختر المندوب:", options=list(driver_options.keys()), format_func=lambda x: driver_options[x])
        
        info = get_driver_info(selected_id)
        balance = info['balance']
        
        st.markdown(f"**المندوب الحالي:** {info['name']} | **الرصيد الحالي:** **<span style='color:green; font-size: 1.5em;'>{balance} أوقية</span>**", unsafe_allow_html=True)
        st.divider()
        
        tab1, tab2 = st.tabs(["✅ إتمام توصيلة", "💰 شحن رصيد"])
        
        with tab1:
            st.markdown(f"سيتم خصم **{DEDUCTION_AMOUNT} أوقية** من الرصيد.")
            if st.button("تسجيل توصيلة ناجحة", key="deduct_button", type="primary"):
                if balance >= DEDUCTION_AMOUNT:
                    new_bal = update_balance(selected_id, -DEDUCTION_AMOUNT, "خصم توصيلة")
                    st.success(f"تم تسجيل التوصيلة! الرصيد المتبقي: {new_bal} أوقية")
                    st.rerun()
                else:
                    st.error("عفواً، الرصيد غير كافي لإجراء التوصيلة. يرجى الشحن أولاً.")
        
        with tab2:
            amount_to_add = st.number_input("المبلغ المراد شحنه (أوقية)", min_value=1.0, step=10.0, key="charge_amount")
            if st.button("تأكيد الشحن", key="charge_button"):
                new_bal = update_balance(selected_id, amount_to_add, "شحن رصيد")
                st.success(f"تم الشحن بنجاح! الرصيد الجديد: {new_bal} أوقية")
                st.rerun()

# ----------------------------------------------------------------------------------
# 4. إدارة المندوبين (إضافة/تعديل) (تظهر للمسؤول فقط)
# ----------------------------------------------------------------------------------
elif current_menu == "إدارة المندوبين (إضافة/تعديل)":
    st.header("إدارة بيانات المندوبين")
    # (كود إدارة المندوبين بالكامل يوضع هنا)
    tab_add, tab_edit, tab_view = st.tabs(["إضافة مندوب", "تعديل بيانات", "عرض الكل"])
    
    with tab_add:
        st.subheader("تسجيل مندوب جديد")
        with st.form("new_driver_form"):
            col1_add, col2_add = st.columns(2)
            with col1_add:
                new_driver_id = st.text_input("ترقيم المندوب (ID)", help="يجب أن يكون رقماً فريداً أو كوداً مميزاً")
                new_name = st.text_input("اسم المندوب الكامل")
                new_bike_plate = st.text_input("رقم لوحة الدراجة")
            with col2_add:
                new_whatsapp = st.text_input("رقم الواتساب (للتواصل)")
                new_notes = st.text_area("ملاحظات إضافية")
                new_is_active = st.checkbox("حساب مفعل؟", value=True, help="عطّل هذا الخيار لمنع المندوب من إجراء عمليات توصيل أو شحن.")
            
            submitted = st.form_submit_button("إضافة المندوب", type="primary")
            if submitted:
                if new_driver_id and new_name:
                    add_driver(new_driver_id, new_name, new_bike_plate, new_whatsapp, new_notes, new_is_active)
                    st.rerun()
                else:
                    st.error("يرجى إدخال ترقيم المندوب والاسم على الأقل.")

    with tab_edit:
        st.subheader("تعديل بيانات مندوب حالي")
        all_drivers = get_drivers(active_only=False)
        if not all_drivers.empty:
            driver_options = all_drivers.set_index('driver_id')['display_name'].to_dict()
            selected_id = st.selectbox("اختر المندوب لتعديل بياناته:", options=list(driver_options.keys()), format_func=lambda x: driver_options[x], key="edit_driver_select")
            
            if selected_id:
                conn = sqlite3.connect(DB_NAME)
                info_db = conn.cursor().execute("SELECT name, bike_plate, whatsapp, notes, is_active FROM drivers WHERE driver_id=?", (selected_id,)).fetchone()
                conn.close()
                
                with st.form("edit_driver_form"):
                    col1_edit, col2_edit = st.columns(2)
                    with col1_edit:
                        edit_name = st.text_input("الاسم", value=info_db[0])
                        edit_bike_plate = st.text_input("رقم لوحة الدراجة", value=info_db[1] if info_db[1] else "")
                        edit_whatsapp = st.text_input("رقم الواتساب", value=info_db[2] if info_db[2] else "")
                    with col2_edit:
                        edit_notes = st.text_area("ملاحظات إضافية", value=info_db[3] if info_db[3] else "")
                        edit_is_active = st.checkbox("حساب مفعل؟", value=info_db[4], help="عطّل لمنع إجراء أي عمليات.")
                    
                    submitted_edit = st.form_submit_button("حفظ التعديلات", type="primary")
                    if submitted_edit:
                        update_driver_details(selected_id, edit_name, edit_bike_plate, edit_whatsapp, edit_notes, edit_is_active)
                        st.rerun()
        else:
            st.info("لا يوجد مندوبين مسجلين بعد.")

    with tab_view:
        st.subheader("عرض بيانات جميع المندوبين")
        all_details = get_all_drivers_details()
        if not all_details.empty:
            st.dataframe(all_details, use_container_width=True)
        else:
            st.info("لا توجد بيانات لعرضها.")

# ----------------------------------------------------------------------------------
# 5. التقارير وسجل العمليات (تظهر للمسؤول فقط)
# ----------------------------------------------------------------------------------
elif current_menu == "التقارير وسجل العمليات":
    st.header("سجل الحركات المالية والتقارير")
    # (كود التقارير بالكامل يوضع هنا)
    report_type = st.radio("نوع التقرير", ["سجل جميع العمليات", "سجل مندوب معين"], horizontal=True)
    
    if report_type == "سجل جميع العمليات":
        st.subheader("جميع حركات الشحن والخصم")
        df = get_history(driver_id=None)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="تحميل السجل كملف CSV",
                data=csv,
                file_name=f"سجل_العمليات_الكامل_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.info("لا توجد حركات مسجلة بعد.")
            
    elif report_type == "سجل مندوب معين":
        active_drivers_df = get_drivers(active_only=False)
        if not active_drivers_df.empty:
            driver_options = active_drivers_df.set_index('driver_id')['display_name'].to_dict()
            selected_id_history = st.selectbox("اختر المندوب لعرض السجل:", options=list(driver_options.keys()), format_func=lambda x: driver_options[x])
            
            st.subheader(f"سجل حركات المندوب: {driver_options[selected_id_history]}")
            df = get_history(driver_id=selected_id_history)
            
            if not df.empty:
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="تحميل السجل كملف CSV",
                    data=csv,
                    file_name=f"سجل_المندوب_{selected_id_history}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )
            else:
                st.info("لا توجد حركات مسجلة لهذا المندوب.")