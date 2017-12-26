/* eslint-disable */
// rename this file from _test_[name] to test_[name] to activate
// and remove above this line

QUnit.test("test: Customer", function (assert) {
	let done = assert.async();

	// number of asserts
	assert.expect(1);

<<<<<<< HEAD
	frappe.run_serially('Customer', [
		// insert a new Customer
		() => frappe.tests.make([
=======
	frappe.run_serially([
		// insert a new Customer
		() => frappe.tests.make('Customer', [
>>>>>>> ff2fb653be48d5fcff03b6b0c51917e35358b2fd
			// values to be set
			{key: 'value'}
		]),
		() => {
			assert.equal(cur_frm.doc.key, 'value');
		},
		() => done()
	]);

});
