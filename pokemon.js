// Scripts to help fill out pokemon forms easily
function dob() {
	$("#id_dob").val("1980-05-05")
	$("form[name='verify-age'").submit()
}

function formFill(number) {
	if (number < 10) {
		number = "0"+number
	}
	$("#id_username").val("PokeHack"+number)
	$("#id_password").val("password1")
	$("#id_confirm_password").val($("#id_password").val())
	$("#id_email").val("halo.zero00+"+number+"@gmail.com")
	$("#id_confirm_email").val($("#id_email").val())
	$("#id_public_profile_opt_in_1").val(true)
	$("#id_terms").click()
}