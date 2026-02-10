app_name = "nexport"
app_title = "NexPort"
app_publisher = "NexPort"
app_description = "NexPort - Dual-Track ERP on Frappe Framework v15"
app_email = "info@nexport.app"
app_license = "MIT"
required_apps = ["frappe"]

# Fixtures
fixtures = ["Role"]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/nexport/css/nexport.css"
# app_include_js = "/assets/nexport/js/nexport.js"

# include js, css files in header of web template
# web_include_css = "/assets/nexport/css/nexport.css"
# web_include_js = "/assets/nexport/js/nexport.js"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# Scheduled Tasks
# ---------------

scheduler_events = {
	# "daily": [
	# 	"nexport.tasks.daily"
	# ],
	# "cron": {
	# 	"0 0 * * *": [
	# 		"nexport.tasks.midnight"
	# 	]
	# },
}

# Document Events
# ---------------

doc_events = {}

# Override Methods
# ----------------

override_whitelisted_methods = {}
