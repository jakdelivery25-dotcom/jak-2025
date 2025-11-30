import streamlit as st
import pandas as pd
from datetime import datetime
import os
import io

# 🆕 استيراد أداة الاتصال بـ Google Sheets
from streamlit_gsheets import GSheetsConnection 

# --- إعدادات التطبيق ---
DEDUCTION_AMOUNT = 15.0  # المبلغ المخصوم لكل توصيلة (أوقية)
ADMIN_KEY = "jak2831" # المفتاح السري للإدارة
IMAGE_PATH = "logo.png" # اسم ملف الشعار الثابت

# 🚨 إعدادات Google Sheets (يجب أن تتطابق مع ملفك ومفتاحك)
SPREADSHEET_NAME = "Delivery_Data_DB" 
CONN_NAME = "gcp_service_account" # اسم الاتصال في secrets.toml
# -----------------------------

# 🆕 دالة مساعدة لتشغيل صوت تنبيه
def play_sound(sound_file):
    """يشغل ملف صوتي باستخدام HTML."""
    # 1. تأكد من إنشاء مجلد static أولاً
    os.makedirs("static", exist_ok=True)
    
    full_path = f"static/{sound_file}" 
    try:
        # 2. الآن تحقق من وجود الملف داخل المجلد
        if os.path.exists(full_path):
            audio_html = f"""
            <audio autoplay="true">
                <source src="{full_path}" type="audio/mp3">
            </audio>
            """
            st.markdown(audio_html, unsafe_allow_html=True)
    except Exception:
        pass

# --- دوال التعامل مع Google Sheets ---

# 🆕 دالة للحصول على الاتصال (يتم تخزينها مؤقتاً لتسريع الأداء)
@st.cache_resource(ttl=3600) 
def get_connection():
    # التأكد من أن المفتاح السري موجود قبل المحاولة
    if CONN_NAME not in st.secrets:
        st.error(f"خطأ: مفتاح الاتصال '{CONN_NAME}' غير موجود في ملف secrets.toml.")
        st.stop()
    return st.connection(CONN_NAME, type=GSheetsConnection)

# 🆕 دالة قراءة ورقة معينة
@st.cache_data(ttl=5) # تحديث البيانات من Sheet كل 5 ثواني
def get_sheet_data(sheet_name):
    conn = get_connection()
    df = conn.read(spreadsheet=SPREADSHEET_NAME, worksheet=sheet_name)
    # تنظيف البيانات وتجهيزها
    if df.empty:
        # إذا كانت الورقة فارغة، أعد DataFrame فارغاً بالأعمدة الصحيحة
        if sheet_name == "drivers":
            return pd.DataFrame(columns=['driver_id', 'name', 'bike_plate', 'whatsapp', 'notes', 'is_active', 'balance'])
        elif sheet_name == "transactions":
            return pd.DataFrame(columns=['driver_name', 'amount', 'type', 'timestamp'])

    # تحويل الأنواع الأساسية
    if 'driver_id' in df.columns:
        df['driver_id'] = df['driver_id'].astype(str)
    if 'is_active' in df.columns:
        df['is_active'] = df['is_active'].astype(bool)
    if 'balance' in df.columns:
        # محاولة تحويل الرصيد إلى رقم، واستبدال الأخطاء بصفر
        df['balance'] = pd.to_numeric(df['balance'], errors='coerce').fillna(0.0) 
    if 'amount' in df.columns:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        
    return df

# 🚨 تم استبدال init_db بالتحقق من الاتصال
def init_db():
    try:
        get_sheet_data("drivers")
    except Exception as e:
        st.error(f"خطأ في الاتصال بـ Google Sheets: الرجاء التأكد من اسم الملف '{SPREADSHEET_NAME}' ووجود ورقتي 'drivers' و 'transactions'.")
        st.error(f"تفاصيل الخطأ: {e}")
        st.stop()

# 🆕 دالة لإضافة مندوب جديد (تكتب في Sheet)
def add_driver(driver_id, name, bike_plate, whatsapp, notes, is_active):
    drivers_df = get_sheet_data("drivers")
    
    # 2. التحقق من التكرار
    if driver_id in drivers_df['driver_id'].values:
        st.error("رقم الترقيم (ID) هذا موجود مسبقاً. 🚨")
        play_sound("error.mp3") 
        return
        
    # 3. إنشاء الصف الجديد
    new_driver = pd.DataFrame([{
        "driver_id": driver_id, 
        "name": name, 
        "bike_plate": bike_plate, 
        "whatsapp": whatsapp, 
        "notes": notes, 
        "is_active": is_active, 
        "balance": 0.0
    }])
    
    # 4. دمج وحفظ البيانات الجديدة
    updated_df = pd.concat([drivers_df, new_driver], ignore_index=True)
    conn = get_connection()
    conn.write(spreadsheet=SPREADSHEET_NAME, worksheet="drivers", data=updated_df)
    
    st.cache_data.clear() # مسح ذاكرة التخزين المؤقت للبيانات
    st.success(f"تمت إضافة المندوب '{name}' بنجاح! 🔔")
    play_sound("success.mp3") 

# 🆕 دالة البحث (تقرأ من Sheet)
def search_driver(search_term):
    drivers_df = get_sheet_data("drivers")
    # البحث باستخدام driver_id أو whatsapp
    result = drivers_df[
        (drivers_df['driver_id'] == search_term) | 
        (drivers_df['whatsapp'] == search_term)
    ]
    if not result.empty:
        # إرجاع أول نتيجة مطابقة كقاموس
        row = result.iloc[0]
        return {"driver_id": row['driver_id'], "name": row['name'], "balance": float(row['balance']), "is_active": bool(row['is_active'])}
    return None

# 🆕 دالة جلب معلومات المندوب (تقرأ من Sheet)
def get_driver_info(driver_id):
    drivers_df = get_sheet_data("drivers")
    result = drivers_df[drivers_df['driver_id'] == driver_id]
    if not result.empty:
        row = result.iloc[0]
        return {"name": row['name'], "balance": float(row['balance']), "is_active": bool(row['is_active'])} 
    return None

# 🆕 دالة تحديث التفاصيل (تكتب في Sheet)
def update_driver_details(driver_id, name, bike_plate, whatsapp, notes, is_active):
    conn = get_connection()
    drivers_df = get_sheet_data("drivers")
    
    # تحديد الصف المراد تعديله
    idx = drivers_df[drivers_df['driver_id'] == driver_id].index
    
    if not idx.empty:
        # تطبيق التعديلات
        drivers_df.loc[idx, 'name'] = name
        drivers_df.loc[idx, 'bike_plate'] = bike_plate
        drivers_df.loc[idx, 'whatsapp'] = whatsapp
        drivers_df.loc[idx, 'notes'] = notes
        drivers_df.loc[idx, 'is_active'] = is_active
        
        # إعادة كتابة الجدول بالكامل
        conn.write(spreadsheet=SPREADSHEET_NAME, worksheet="drivers", data=drivers_df)
        st.cache_data.clear()
        st.success(f"تم تحديث بيانات المندوب {name} بنجاح.")

# 🆕 دالة تحديث الرصيد (تكتب في Sheet)
def update_balance(driver_id, amount, trans_type):
    conn = get_connection()
    
    # 1. تحديث جدول drivers (تعديل الرصيد)
    drivers_df = get_sheet_data("drivers")
    
    # التأكد من وجود المندوب
    idx = drivers_df[drivers_df['driver_id'] == driver_id].index
    if idx.empty: return 0.0

    driver_row = drivers_df[drivers_df['driver_id'] == driver_id].iloc[0]
    
    # حساب الرصيد الجديد
    current_balance = float(driver_row['balance'])
    name = driver_row['name']
    new_balance = current_balance + amount
    
    # تعديل القيمة في DataFrame
    drivers_df.loc[idx, 'balance'] = new_balance
    
    # إعادة كتابة جدول drivers بالكامل
    conn.write(spreadsheet=SPREADSHEET_NAME, worksheet="drivers", data=drivers_df)
    
    # 2. تحديث جدول transactions (تسجيل الحركة)
    transactions_df = get_sheet_data("transactions")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_transaction = pd.DataFrame([{
        "driver_name": f"{name} (ID:{driver_id})", 
        "amount": amount, 
        "type": trans_type, 
        "timestamp": timestamp
    }])
    
    # دمج وكتابة سجل الحركات
    updated_transactions = pd.concat([transactions_df, new_transaction], ignore_index=True)
    conn.write(spreadsheet=SPREADSHEET_NAME, worksheet="transactions", data=updated_transactions)
    
    st.cache_data.clear() # مسح ذاكرة التخزين المؤقت بعد التحديث
    return new_balance

# 🆕 دالة جلب عدد التوصيلات (تقرأ من Sheet)
def get_deliveries_count_per_driver():
    transactions_df = get_sheet_data("transactions")
    if transactions_df.empty: return pd.DataFrame(columns=['driver_id', 'عدد التوصيلات'])

    # استخلاص الـ driver_id من driver_name
    transactions_df['driver_id'] = transactions_df['driver_name'].str.extract(r'ID:(\w+)\)')
    
    deliveries_count = transactions_df[transactions_df['type'] == 'خصم توصيلة'] \
        .groupby('driver_id') \
        .size() \
        .reset_index(name='عدد التوصيلات')
        
    return deliveries_count

# 🆕 دالة جلب الإجماليات (تقرأ من Sheet)
def get_totals():
    drivers_df = get_sheet_data("drivers")
    transactions_df = get_sheet_data("transactions")
    
    total_balance = drivers_df['balance'].sum()
    
    total_charged = transactions_df[transactions_df['type'] == 'شحن رصيد']['amount'].sum()
    
    total_deducted_negative = transactions_df[transactions_df['type'] == 'خصم توصيلة']['amount'].sum()
    total_deducted = abs(total_deducted_negative)
    total_deliveries = transactions_df[transactions_df['type'] == 'خصم توصيلة'].shape[0]
    
    return total_balance, total_charged, total_deducted, total_deliveries

# 🆕 دالة جلب السجل (تقرأ من Sheet)
def get_history(driver_id=None):
    transactions_df = get_sheet_data("transactions")
    if transactions_df.empty:
         return pd.DataFrame(columns=['المندوب', 'العملية', 'المبلغ', 'التوقيت'])
         
    # تنظيف الأعمدة
    df_history = transactions_df.rename(columns={
        'driver_name': 'المندوب', 
        'amount': 'المبلغ', 
        'type': 'العملية', 
        'timestamp': 'التوقيت'
    })
    
    if driver_id:
        # تصفية حسب ID
        df_history = df_history[df_history['المندوب'].str.contains(f'ID:{driver_id}')]
        # إزالة عمود المندوب في حالة التصفية
        df_history = df_history.drop(columns=['المندوب'])
        
    return df_history.sort_values(by='التوقيت', ascending=False)

# 🆕 دالة جلب تفاصيل الكل (تقرأ من Sheet)
def get_all_drivers_details():
    df = get_sheet_data("drivers")
    if df.empty: return pd.DataFrame()
    
    deliveries_count_df = get_deliveries_count_per_driver()
    
    if not deliveries_count_df.empty:
        df = pd.merge(df, deliveries_count_df, on='driver_id', how='left').fillna({'عدد التوصيلات': 0})
        df['عدد التوصيلات'] = df['عدد التوصيلات'].astype(int)
    else:
        df['عدد التوصيلات'] = 0
        
    df['الحالة'] = df['is_active'].apply(lambda x: 'مفعل' if x == True else 'معطل')
    
    df.rename(columns={
        'driver_id': 'الترقيم',
        'name': 'الاسم',
        'bike_plate': 'رقم اللوحة',
        'whatsapp': 'واتساب',
        'balance': 'الرصيد',
        'notes': 'ملاحظات'
    }, inplace=True)
    
    df.insert(0, 'ت', range(1, 1 + len(df)))
    
    cols = ['ت', 'الترقيم', 'الاسم', 'رقم اللوحة', 'واتساب', 'الرصيد', 'عدد التوصيلات', 'الحالة', 'ملاحظات']
    return df[cols]

# ----------------------------------------------------------------------------------
# 🌐 واجهة التطبيق (لا يوجد تغيير كبير هنا، فقط استخدام الدوال الجديدة)
# ----------------------------------------------------------------------------------
st.set_page_config(page_title="نظام إدارة التوصيل", layout="wide", page_icon="🚚")
st.title("🚚 نظام رصيد المندوبين (Google Sheets)")

# التحقق من الاتصال وتهيئة التطبيق
init_db()

# تهيئة حالة الجلسة
if 'logged_in_driver_id' not in st.session_state:
    st.session_state['logged_in_driver_id'] = None
if 'admin_mode' not in st.session_state:
    st.session_state['admin_mode'] = False
if 'search_result_id' not in st.session_state:
    st.session_state['search_result_id'] = None

# ----------------------------------------------------------------------------------
# 1. منطق القائمة الجانبية
# ----------------------------------------------------------------------------------

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
        st.session_state['search_result_id'] = None
        st.rerun()

elif st.session_state['logged_in_driver_id']:
    # وضع المندوب (Driver)
    driver_id = st.session_state['logged_in_driver_id']
    driver_info = get_driver_info(driver_id)
    if driver_info:
        st.sidebar.markdown(f"**مرحباً، {driver_info['name']}**")
        st.sidebar.button("خروج (Logout)", on_click=lambda: st.session_state.update(logged_in_driver_id=None, admin_mode=False, search_result_id=None))
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
                st.metric(label="الرصيد المتوفر", value=f"{driver_data['balance']:.2f} أوقية", delta_color="off")
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
    
    st.subheader("1. تحديد المندوب")
    
    # --- منطق البحث ---
    col_search, col_button = st.columns([3, 1])
    with col_search:
        search_term_op = st.text_input("ابحث بترقيم المندوب (ID) أو رقم الواتساب", key="search_op_input")
    with col_button:
        if st.button("بحث وتحديد", key="search_op_btn", type="primary"):
            driver_data = search_driver(search_term_op)
            if driver_data:
                st.session_state['search_result_id'] = driver_data['driver_id']
                st.success(f"تم تحديد المندوب: {driver_data['name']}")
            else:
                st.error("لم يتم العثور على المندوب بالترقيم أو رقم الواتساب المدخل.")
                st.session_state['search_result_id'] = None
    # -------------------
    
    selected_id = st.session_state['search_result_id']
    
    if selected_id:
        info = get_driver_info(selected_id)
        if info:
            st.subheader(f"2. تفاصيل ورصيد المندوب: {info['name']}")
            balance = info['balance']
            is_active = info['is_active']
            
            status_text = "🟢 مفعل" if is_active else "🔴 معطل"
            status_color = "green" if is_active else "red"
            
            st.markdown(f"**الرصيد الحالي:** **<span style='color:green; font-size: 1.5em;'>{balance:.2f} أوقية</span>** | **الحالة:** <span style='color:{status_color}; font-size: 1.2em;'>{status_text}</span>", unsafe_allow_html=True)
            st.divider()
            
            if not is_active:
                 st.warning("تنبيه: هذا المندوب **معطل** ولا يمكنه إجراء عمليات توصيل حتى يتم تفعيله من قائمة الإدارة.")

            tab1, tab2 = st.tabs(["✅ إتمام توصيلة", "💰 شحن رصيد"])
            
            with tab1:
                st.markdown(f"سيتم خصم **{DEDUCTION_AMOUNT} أوقية** من الرصيد.")
                if st.button("تسجيل توصيلة ناجحة", key="deduct_button", type="primary", disabled=not is_active):
                    if balance >= DEDUCTION_AMOUNT:
                        new_bal = update_balance(selected_id, -DEDUCTION_AMOUNT, "خصم توصيلة")
                        st.success(f"تم تسجيل التوصيلة! الرصيد المتبقي: {new_bal:.2f} أوقية 🔔")
                        play_sound("success.mp3") 
                        st.session_state['search_result_id'] = None 
                        st.rerun()
                    else:
                        st.error("عفواً، الرصيد غير كافي لإجراء التوصيلة. يرجى الشحن أولاً. 🚨")
                        play_sound("error.mp3") 
            
            with tab2:
                amount_to_add = st.number_input("المبلغ المراد شحنه (أوقية)", min_value=-99999.0, step=10.0, key="charge_amount")
                if st.button("تأكيد الشحن", key="charge_button"):
                    new_bal = update_balance(selected_id, amount_to_add, "شحن رصيد")
                    st.success(f"تم الشحن بنجاح! الرصيد الجديد: {new_bal:.2f} أوقية 🔔")
                    play_sound("success.mp3") 
                    st.session_state['search_result_id'] = None 
                    st.rerun()
        else:
            st.error("حدث خطأ في جلب بيانات المندوب المحدد.")
    else:
        st.info("يرجى البحث عن المندوب باستخدام ترقيمه أو رقم الواتساب لتسجيل عملية.")

# ----------------------------------------------------------------------------------
# 4. إدارة المندوبين (إضافة/تعديل)
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
        
        # --- منطق البحث هنا ---
        col_search_edit, col_button_edit = st.columns([3, 1])
        with col_search_edit:
            search_term_edit = st.text_input("ابحث بترقيم المندوب (ID) أو رقم الواتساب للتعديل", key="search_edit_input")
        with col_button_edit:
            if st.button("بحث وتحديد", key="search_edit_btn", type="primary"):
                driver_data = search_driver(search_term_edit)
                if driver_data:
                    st.session_state['search_result_id'] = driver_data['driver_id']
                    st.success(f"تم تحديد المندوب: {driver_data['name']}. يمكنك الآن التعديل.")
                else:
                    st.error("لم يتم العثور على المندوب.")
                    st.session_state['search_result_id'] = None
        # ----------------------
        
        selected_id = st.session_state['search_result_id']
        
        if selected_id:
            info = get_driver_info(selected_id)
            if info:
                st.markdown(f"**بيانات المندوب الحالي: {info['name']}**")
                
                # جلب البيانات التفصيلية من DataFrame
                drivers_df = get_sheet_data("drivers")
                driver_row = drivers_df[drivers_df['الترقيم'] == selected_id].iloc[0]
                
                with st.form("edit_driver_form"):
                    col1_edit, col2_edit = st.columns(2)
                    with col1_edit:
                        edit_name = st.text_input("الاسم", value=driver_row['name'])
                        edit_bike_plate = st.text_input("رقم لوحة الدراجة", value=driver_row['bike_plate'] if driver_row['bike_plate'] else "")
                        edit_whatsapp = st.text_input("رقم الواتساب", value=driver_row['whatsapp'] if driver_row['whatsapp'] else "")
                    with col2_edit:
                        edit_notes = st.text_area("ملاحظات إضافية", value=driver_row['notes'] if driver_row['notes'] else "")
                        edit_is_active = st.checkbox("حساب مفعل؟", value=bool(driver_row['is_active']), help="عطّل لمنع إجراء أي عمليات.")
                    
                    submitted_edit = st.form_submit_button("حفظ التعديلات", type="primary")
                    if submitted_edit:
                        update_driver_details(selected_id, edit_name, edit_bike_plate, edit_whatsapp, edit_notes, edit_is_active)
                        st.session_state['search_result_id'] = None 
                        st.rerun()
            else:
                 st.error("حدث خطأ في جلب بيانات المندوب للتعديل.")
        else:
            st.info("يرجى استخدام شريط البحث أعلاه لتحديد المندوب المراد تعديله.")

    with tab_view:
        st.subheader("عرض بيانات جميع المندوبين")
        all_details = get_all_drivers_details()
        if not all_details.empty:
            st.dataframe(all_details, use_container_width=True)
        else:
            st.info("لا توجد بيانات لعرضها.")

# ----------------------------------------------------------------------------------
# 5. التقارير وسجل العمليات
# ----------------------------------------------------------------------------------
elif current_menu == "التقارير وسجل العمليات":
    st.header("سجل الحركات المالية والتقارير")
    
    report_type = st.radio("نوع التقرير", ["التقارير الإجمالية", "سجل جميع العمليات", "سجل مندوب معين"], horizontal=True)
    
    if report_type == "التقارير الإجمالية":
        st.subheader("ملخص إجمالي للنظام")
        total_balance, total_charged, total_deducted, total_deliveries = get_totals()
        
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

        with col_total_deliveries:
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
        st.subheader("البحث وعرض سجل مندوب محدد")
        
        # --- منطق البحث هنا ---
        col_search_hist, col_button_hist = st.columns([3, 1])
        with col_search_hist:
            search_term_hist = st.text_input("ابحث بترقيم المندوب (ID) أو رقم الواتساب", key="search_hist_input")
        with col_button_hist:
            if st.button("بحث وعرض السجل", key="search_hist_btn", type="primary"):
                driver_data = search_driver(search_term_hist)
                if driver_data:
                    st.session_state['search_result_id'] = driver_data['driver_id']
                    st.success(f"تم تحديد المندوب: {driver_data['name']}")
                else:
                    st.error("لم يتم العثور على المندوب.")
                    st.session_state['search_result_id'] = None
        # ----------------------
        
        selected_id = st.session_state['search_result_id']
        
        if selected_id:
            driver_info = get_driver_info(selected_id)
            if driver_info:
                driver_name = driver_info['name']
                st.markdown(f"**سجل حركات المندوب: {driver_name} (ID: {selected_id})**")
                df = get_history(driver_id=selected_id)
                
                if not df.empty:
                    st.dataframe(df, use_container_width=True)
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="تحميل السجل كملف CSV",
                        data=csv,
                        file_name=f"سجل_المندوب_{selected_id}_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                    )
                else:
                    st.info("لا توجد حركات مسجلة لهذا المندوب.")
            else:
                 st.error("تعذر جلب بيانات المندوب.")
        else:
            st.info("يرجى استخدام شريط البحث أعلاه لتحديد المندوب المطلوب.")


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
            st.rerun() 

        except Exception as e:
            st.error(f"حدث خطأ أثناء حفظ الملف: {e}")