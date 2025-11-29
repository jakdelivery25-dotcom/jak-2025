import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
import io

# --- إعدادات التطبيق ---
DEDUCTION_AMOUNT = 15.0  # المبلغ المخصوم لكل توصيلة (أوقية)
DB_NAME = "delivery_app.db"
ADMIN_KEY = "jak2831" # المفتاح السري للإدارة
IMAGE_PATH = "logo.png" # اسم ملف الشعار الثابت

# --- دوال التعامل مع قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS drivers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, driver_id TEXT UNIQUE, name TEXT, bike_plate TEXT, whatsapp TEXT, notes TEXT, is_active BOOLEAN, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, driver_name TEXT, amount REAL, type TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

# 🆕 دالة لحساب عدد التوصيلات لكل مندوب
def get_deliveries_count_per_driver():
    conn = sqlite3.connect(DB_NAME)
    # نستخدم دوال SQLite (SUBSTR, INSTR) لاستخراج ID من اسم المندوب المخزن 'Name (ID:XX)'
    query = """
    SELECT 
        SUBSTR(driver_name, INSTR(driver_name, ':')+1, LENGTH(driver_name)-INSTR(driver_name, ':')-1) AS driver_id, 
        COUNT(*) AS 'عدد التوصيلات'
    FROM transactions
    WHERE type='خصم توصيلة'
    GROUP BY driver_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# 🆕 دالة محدثة لحساب الإجمالي (تم إضافة total_deliveries)
def get_totals():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. مجموع الرصيد الحالي لجميع المندوبين
    total_balance = c.execute("SELECT SUM(balance) FROM drivers").fetchone()[0] or 0.0
    
    # 2. مجموع الشحن
    total_charged = c.execute("SELECT SUM(amount) FROM transactions WHERE type='شحن رصيد'").fetchone()[0] or 0.0
    
    # 3. مجموع الخصومات (القيمة المطلقة للقيمة السالبة المخزنة)
    total_deducted_negative = c.execute("SELECT SUM(amount) FROM transactions WHERE type='خصم توصيلة'").fetchone()[0] or 0.0
    total_deducted = abs(total_deducted_negative)
    
    # 4. عدد التوصيلات الإجمالي 🆕
    total_deliveries = c.execute("SELECT COUNT(*) FROM transactions WHERE type='خصم توصيلة'").fetchone()[0] or 0
    
    conn.close()
    return total_balance, total_charged, total_deducted, total_deliveries # ⬅️ يتم إرجاع 4 قيم

# --- الدوال المتبقية ---

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

def get_drivers(active_only=True):
    conn = sqlite3.connect(DB_NAME)
    if active_only:
        df = pd.read_sql_query("SELECT driver_id, name, balance FROM drivers WHERE is_active=1", conn)
    else:
        df = pd.read_sql_query("SELECT driver_id, name, balance FROM drivers", conn)
    conn.close()
    df['display_name'] = df['name'] + ' (ID: ' + df['driver_id'] + ')'
    return df

def get_driver_info(driver_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name, balance, is_active FROM drivers WHERE driver_id=?", (driver_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {"name": result[0], "balance": result[1], "is_active": result[2]} 
    return None

def update_driver_details(driver_id, name, bike_plate, whatsapp, notes, is_active):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE drivers SET name=?, bike_plate=?, whatsapp=?, notes=?, is_active=? WHERE driver_id=?", 
              (name, bike_plate, whatsapp, notes, is_active, driver_id))
    conn.commit()
    conn.close()
    st.success(f"تم تحديث بيانات المندوب {name} بنجاح.")

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

def get_history(driver_id=None):
    conn = sqlite3.connect(DB_NAME)
    if driver_id:
        query = f"SELECT type as 'العملية', amount as 'المبلغ', timestamp as 'التوقيت' FROM transactions WHERE driver_name LIKE '%ID:{driver_id}%' ORDER BY id DESC"
    else:
        query = "SELECT driver_name as 'المندوب', type as 'العملية', amount as 'المبلغ', timestamp as 'التوقيت' FROM transactions ORDER BY id DESC"
        
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# 🆕 دالة محدثة (تمت إضافة عد التوصيلات وتصحيح التسلسل)
def get_all_drivers_details():
    conn = sqlite3.connect(DB_NAME)
    # 1. جلب البيانات الأساسية
    df = pd.read_sql_query("SELECT driver_id, name as 'الاسم', bike_plate as 'رقم اللوحة', whatsapp as 'واتساب', balance as 'الرصيد', is_active as 'الحالة', notes as 'ملاحظات' FROM drivers", conn)
    conn.close()
    
    # 2. إضافة عدد التوصيلات 🆕
    deliveries_count_df = get_deliveries_count_per_driver()
    if not deliveries_count_df.empty:
        # دمج البيانات بناءً على driver_id، وملء القيم الفارغة (للمندوبين الذين لم يقوموا بتوصيلات بعد) بالصفر
        df = pd.merge(df, deliveries_count_df, on='driver_id', how='left').fillna({'عدد التوصيلات': 0})
        # تحويل عدد التوصيلات إلى عدد صحيح (integer) بعد التعبئة
        df['عدد التوصيلات'] = df['عدد التوصيلات'].astype(int)
    else:
        df['عدد التوصيلات'] = 0
        
    # 3. تعديل عمود الحالة
    df['الحالة'] = df['الحالة'].apply(lambda x: 'مفعل' if x == 1 else 'معطل')
    
    # 4. تصحيح الترقيم (العد يبدأ من 1) 🆕
    df.insert(0, 'ت', range(1, 1 + len(df)))
    
    # 5. إعادة تسمية العمود
    df.rename(columns={'driver_id': 'الترقيم'}, inplace=True)
    
    # ترتيب الأعمدة للعرض
    cols = ['ت', 'الترقيم', 'الاسم', 'رقم اللوحة', 'واتساب', 'الرصيد', 'عدد التوصيلات', 'الحالة', 'ملاحظات']
    
    return df[cols]
# --- نهاية الدوال المتبقية ---


# --- واجهة التطبيق ---
st.set_page_config(page_title="نظام إدارة التوصيل", layout="wide", page_icon="jak.png")
st.title("jak.png نظام رصيد المندوبين")

# التأكد من وجود قاعدة البيانات
init_db()

# تهيئة حالة الجلسة
if 'logged_in_driver_id' not in st.session_state:
    st.session_state['logged_in_driver_id'] = None
if 'admin_mode' not in st.session_state:
    st.session_state['admin_mode'] = False

# ----------------------------------------------------------------------------------
# 1. منطق القائمة الجانبية (مع عرض الصورة)
# ----------------------------------------------------------------------------------

# عرض الصورة في البداية
if os.path.exists(IMAGE_PATH):
    st.sidebar.image(IMAGE_PATH, use_column_width=True)

st.sidebar.header("لوحة التحكم")

if st.session_state['admin_mode']:
    # وضع المسؤول (Admin)
    st.sidebar.markdown("**وضع المسؤول (ADMIN)**")
    menu_options = ["واجهة العمليات (الإدارة)", "إدارة المندوبين (إضافة/تعديل)", "التقارير وسجل العمليات", "إعدادات التطبيق (الشعار)", "الخروج من وضع المسؤول"]
    current_menu = st.sidebar.radio("القائمة", menu_options)
    if current_menu == "الخروج من وضع المسؤول":
        st.session_state['admin_mode'] = False
        st.rerun()

elif st.session_state['logged_in_driver_id']:
    # وضع المندوب (Driver)
    driver_id = st.session_state['logged_in_driver_id']
    driver_info = get_driver_info(driver_id)
    if driver_info:
        st.sidebar.markdown(f"**مرحباً، {driver_info['name']}**")
        st.sidebar.button("خروج (Logout)", on_click=lambda: st.session_state.update(logged_in_driver_id=None, admin_mode=False))
        current_menu = "واجهة المندوب"
    else:
        st.session_state.logged_in_driver_id = None
        current_menu = "واجهة المندوب"

else:
    # وضع الزائر (Guest)
    current_menu = "واجهة المندوب"
    
    # مدخل المسؤول الإداري 
    st.sidebar.divider()
    with st.sidebar.expander("مدخل المسؤول الإداري"):
        admin_key_input = st.text_input("أدخل المفتاح السري", type="password")
        if st.button("دخول المسؤول"):
            if admin_key_input == ADMIN_KEY:
                st.session_state['admin_mode'] = True
                st.rerun()
            else:
                st.error("المفتاح السري غير صحيح.")

# ----------------------------------------------------------------------------------
# 2. واجهة المندوب
# ----------------------------------------------------------------------------------
if current_menu == "واجهة المندوب":
    if st.session_state['logged_in_driver_id']:
        driver_id = st.session_state['logged_in_driver_id']
        driver_data = get_driver_info(driver_id)
        
        if driver_data:
            st.header(f"أهلاً بك يا {driver_data['name']}!")
            
            is_active = driver_data['is_active']
            status_text = "🟢 مفعل" if is_active else "🔴 معطل"
            status_color = "green" if is_active else "red"
            st.markdown(f"**حالة حسابك:** <span style='color:{status_color}; font-size: 1.5em;'>{status_text}</span>", unsafe_allow_html=True)
            
            if is_active:
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
                st.error("عفواً، حسابك معطل. لا يمكنك إجراء أي عمليات. يرجى مراجعة الإدارة.")
            
        else:
            st.error("حدث خطأ في جلب البيانات.")
            st.session_state['logged_in_driver_id'] = None
            st.rerun()
    
    else:
        st.header("تسجيل الدخول للمندوبين")
        driver_id_input = st.text_input("أدخل ترقيمك (Driver ID)")
        
        def attempt_login():
            if not driver_id_input:
                st.error("الرجاء إدخال ترقيمك.")
                return
            
            info = get_driver_info(driver_id_input)
            if info:
                st.session_state['logged_in_driver_id'] = driver_id_input
                st.success(f"تم تسجيل الدخول بنجاح! مرحباً بك يا {info['name']}.")
                st.rerun()
            else:
                st.error("ترقيم المندوب غير صحيح.")

        st.button("تسجيل الدخول", on_click=attempt_login, type="primary")

# ----------------------------------------------------------------------------------
# 3. واجهة العمليات (الإدارة)
# ----------------------------------------------------------------------------------
elif current_menu == "واجهة العمليات (الإدارة)":
    st.header("تسجيل العمليات (شحن/خصم)")
    
    active_drivers_df = get_drivers(active_only=False)
    if active_drivers_df.empty:
        st.warning("لا يوجد مندوبون مسجلون حالياً.")
    else:
        driver_options = active_drivers_df.set_index('driver_id')['display_name'].to_dict()
        selected_id = st.selectbox("اختر المندوب:", options=list(driver_options.keys()), format_func=lambda x: driver_options[x])
        
        info = get_driver_info(selected_id)
        balance = info['balance']
        is_active = info['is_active']
        
        status_text = "🟢 مفعل" if is_active else "🔴 معطل"
        status_color = "green" if is_active else "red"
        
        st.markdown(f"**المندوب الحالي:** {info['name']} | **الرصيد الحالي:** **<span style='color:green; font-size: 1.5em;'>{balance} أوقية</span>** | **الحالة:** <span style='color:{status_color}; font-size: 1.2em;'>{status_text}</span>", unsafe_allow_html=True)
        st.divider()
        
        if not is_active:
             st.warning("تنبيه: هذا المندوب **معطل** ولا يمكنه إجراء عمليات توصيل حتى يتم تفعيله من قائمة الإدارة.")

        tab1, tab2 = st.tabs(["✅ إتمام توصيلة", "💰 شحن رصيد"])
        
        with tab1:
            st.markdown(f"سيتم خصم **{DEDUCTION_AMOUNT} أوقية** من الرصيد.")
            if st.button("تسجيل توصيلة ناجحة", key="deduct_button", type="primary", disabled=not is_active):
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
# 4. إدارة المندوبين (تم تحديث عرض الكل)
# ----------------------------------------------------------------------------------
elif current_menu == "إدارة المندوبين (إضافة/تعديل)":
    st.header("إدارة بيانات المندوبين")
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
            # ⬅️ هذا التقرير الآن يشمل التسلسل (ت) وعدد التوصيلات لكل مندوب
            st.dataframe(all_details, use_container_width=True)
        else:
            st.info("لا توجد بيانات لعرضها.")

# ----------------------------------------------------------------------------------
# 5. التقارير وسجل العمليات (تم تحديث التقارير الإجمالية)
# ----------------------------------------------------------------------------------
elif current_menu == "التقارير وسجل العمليات":
    st.header("سجل الحركات المالية والتقارير")
    
    report_type = st.radio("نوع التقرير", ["التقارير الإجمالية", "سجل جميع العمليات", "سجل مندوب معين"], horizontal=True)
    
    if report_type == "التقارير الإجمالية":
        st.subheader("ملخص إجمالي للنظام")
        # ⬅️ استلام 4 قيم من الدالة
        total_balance, total_charged, total_deducted, total_deliveries = get_totals()
        
        # ⬅️ إنشاء 4 أعمدة للعرض
        col_total_bal, col_total_charged, col_total_deducted, col_total_deliveries = st.columns(4)
        
        with col_total_bal:
            st.metric(label="مجموع الأرصدة الحالية للمندوبين", value=f"{total_balance:.2f} أوقية", delta_color="off")
            st.caption("مجموع الرصيد الحالي الموجود في حسابات جميع المندوبين.")
        
        with col_total_charged:
            st.metric(label="إجمالي المبالغ المشحونة", value=f"{total_charged:.2f} أوقية", delta_color="off")
            st.caption("مجموع كل عمليات الشحن التي تمت منذ بدء النظام.")
        
        with col_total_deducted:
            st.metric(label="إجمالي المبالغ المخصومة", value=f"{total_deducted:.2f} أوقية", delta_color="off")
            st.caption("مجموع الخصومات التي تمت لتسجيل التوصيلات.")

        with col_total_deliveries: # 🆕 الإجمالي الجديد
            st.metric(label="عدد التوصيلات الإجمالي", value=f"{total_deliveries}", delta_color="off")
            st.caption("مجموع عدد التوصيلات الناجحة المسجلة في النظام.")
        
    elif report_type == "سجل جميع العمليات":
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

# ----------------------------------------------------------------------------------
# 6. إعدادات التطبيق (الشعار)
# ----------------------------------------------------------------------------------
elif current_menu == "إعدادات التطبيق (الشعار)":
    st.header("تغيير شعار الشركة")
    st.markdown("يمكنك رفع ملف صورة جديد (PNG أو JPG) ليحل محل الشعار الحالي في الواجهة الجانبية.")
    
    # معاينة الشعار الحالي
    if os.path.exists(IMAGE_PATH):
        st.image(IMAGE_PATH, caption='الشعار الحالي', width=200)
    else:
        st.info("لا يوجد شعار حالي. يرجى رفع شعار جديد.")
        
    uploaded_file = st.file_uploader("اختر صورة الشعار (PNG أو JPG)", type=["png", "jpg", "jpeg"])
    
    if uploaded_file is not None:
        image_bytes = uploaded_file.read()
        
        try:
            with open(IMAGE_PATH, "wb") as f:
                f.write(image_bytes)
            
            st.success("✅ تم رفع وحفظ الشعار الجديد بنجاح!")
            st.info("لتظهر التحديثات بالكامل، قد تحتاج إلى الضغط على خيار آخر في القائمة الجانبية.")
            
            st.image(IMAGE_PATH, caption='معاينة الشعار الجديد', width=200)

        except Exception as e:
            st.error(f"حدث خطأ أثناء حفظ الملف: {e}")