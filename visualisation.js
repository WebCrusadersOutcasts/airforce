// Add event listeners to dropdowns
document.getElementById("date").addEventListener("change", fetchData);
document.getElementById("aircraft").addEventListener("change", fetchData);
document.getElementById("sortie").addEventListener("change", fetchData);

// Function to fetch data based on selected dropdown value
function fetchData() {
  const selectedDate = document.getElementById("date").value;
  const selectedAircraft = document.getElementById("aircraft").value;
  const selectedSortie = document.getElementById("sortie").value;

  // Make an AJAX request to Flask server
  fetch('/fetch_data', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      date: selectedDate,
      aircraft: selectedAircraft,
      sortie: selectedSortie
    })
  })
  .then(response => response.json())
  .then(data => {
    // Assuming data is received and processed
    // Call a function to display graph with the received data
    displayGraph(data);
  })
  .catch(error => {
    console.error('Error fetching data:', error);
  });
}

// Function to display graph using the received data
function displayGraph(data) {
  // Implement graph display logic here using a library like Chart.js
  // Example: Create a Chart.js chart with the received data
}
