function createMatrixRain() {
    const matrixBg = document.getElementById('matrix-bg');
    const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%^&*()_+-=[]{}|;:,.<>?アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';
    
    const columnWidth = 20;
    const numColumns = Math.floor(window.innerWidth / columnWidth);
    
    matrixBg.innerHTML = '';
    
    for (let i = 0; i < numColumns; i++) {
        const column = document.createElement('div');
        column.className = 'matrix-column';
        column.style.left = i * columnWidth + 'px';
        column.style.animationDuration = (Math.random() * 3 + 2) + 's';
        column.style.animationDelay = Math.random() * 2 + 's';
        
        let columnText = '';
        const columnHeight = Math.floor(Math.random() * 20) + 10;
        for (let j = 0; j < columnHeight; j++) {
            columnText += characters.charAt(Math.floor(Math.random() * characters.length)) + '<br>';
        }
        column.innerHTML = columnText;
        
        matrixBg.appendChild(column);
    }
}

createMatrixRain();

window.addEventListener('resize', createMatrixRain);

setInterval(() => {
    const columns = document.querySelectorAll('.matrix-column');
    columns.forEach(column => {
        if (Math.random() < 0.1) {
            const characters = 'ABCDEFGHIJKLMNOPQRSpqrstuvwxyz0123456789@#$%^&*()_+-=[]{}|;:,.<>?アイウクケコフヘホマヤユヨラリルレワヲンАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя';
            let columnText = '';
            const columnHeight = Math.floor(Math.random() * 20) + 10;
            for (let j = 0; j < columnHeight; j++) {
                columnText += characters.charAt(Math.floor(Math.random() * characters.length)) + '<br>';
            }
            column.innerHTML = columnText;
        }
    });
}, 2000);
