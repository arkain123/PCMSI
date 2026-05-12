function loadMetric(agent,metric,canvas) {
    fetch(`/monitoring/api/metrics/${agent}/?metric=${metric}`)
    .then(r=>r.json())
    .then(data=>{
        new Chart(
            document.getElementById(canvas),
            {
                type:'line',
                data:{
                    labels:data.labels,
                    datasets:[{
                        label:metric,
                        data:data.values,
                        tension:0.3
                    }]
                },
                options:{
                    responsive:true,
                    plugins:{
                        legend:{display:false}
                    }
                }
            }
        )
    })
}
