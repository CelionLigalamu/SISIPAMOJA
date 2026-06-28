(function () {
  function getSelectValue(name) {
    var field = document.querySelector('[name="' + name + '"]');
    return field ? field.value : '';
  }

  function calculateAge() {
    var day = parseInt(getSelectValue('date_of_birth_0'), 10);
    var month = parseInt(getSelectValue('date_of_birth_1'), 10);
    var year = parseInt(getSelectValue('date_of_birth_2'), 10);
    var ageField = document.getElementById('id_age_display');

    if (!ageField) {
      return;
    }

    if (!day || !month || !year) {
      ageField.value = '-- years';
      return;
    }

    var today = new Date();
    var age = today.getFullYear() - year;
    var currentMonth = today.getMonth() + 1;
    var currentDay = today.getDate();

    if (currentMonth < month || (currentMonth === month && currentDay < day)) {
      age -= 1;
    }

    ageField.value = age + ' years';
  }

  function bindAgeEvents() {
    ['date_of_birth_0', 'date_of_birth_1', 'date_of_birth_2'].forEach(function (name) {
      var field = document.querySelector('[name="' + name + '"]');
      if (field) {
        field.addEventListener('change', calculateAge);
        field.addEventListener('input', calculateAge);
      }
    });

    calculateAge();
  }

  window.updateMemberAge = calculateAge;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAgeEvents);
  } else {
    bindAgeEvents();
  }
})();
