import '../static/account.css'
import '../static/global.css'
import { Link } from 'react-router-dom'
import MainButton from './components/MainButton'
import { useState } from 'react'

export default function Account(){
    const [isListVisible, setIsListVisible] = useState(false)
    const [projects, setProjects] = useState([])
    const [cards, setCards] = useState([
        { id: 1, type: 'new' },
        { id: 2, type: 'empty' },
        { id: 3, type: 'empty' },
        { id: 4, type: 'empty' },
        { id: 5, type: 'empty' },
        { id: 6, type: 'empty' }
    ])

    const toggleList = () => {
        setIsListVisible(!isListVisible)
    }

    const addProject = (cardId) => {
        const projectName = `Проект ${projects.length + 1}`
        // Случайный прогресс для демонстрации (от 10% до 90%)
        const randomProgress = Math.floor(Math.random() * 80) + 10
        
        const newProject = {
            name: projectName,
            progress: randomProgress,
            id: Date.now() // уникальный ID
        }
        
        setProjects([...projects, newProject])
        
        const updatedCards = cards.map(card => {
            if (card.id === cardId) {
                return { 
                    ...card, 
                    type: 'grid', 
                    name: projectName,
                    progress: randomProgress
                }
            }
            return card
        })
        
        const nextEmptyCard = updatedCards.find(card => card.type === 'empty')
        if (nextEmptyCard) {
            const finalCards = updatedCards.map(card => 
                card.id === nextEmptyCard.id ? { ...card, type: 'new' } : card
            )
            setCards(finalCards)
        } else {
            setCards(updatedCards)
        }
    }

    // Функция для обновления прогресса (будет вызываться из бэкенда)
    // const updateProjectProgress = (projectId, newProgress) => {
    //     // Обновляем прогресс в списке проектов
    //     setProjects(prevProjects => 
    //         prevProjects.map(project => 
    //             project.id === projectId 
    //                 ? { ...project, progress: newProgress }
    //                 : project
    //         )
    //     )
        
    //     // Обновляем прогресс в карточках
    //     setCards(prevCards =>
    //         prevCards.map(card =>
    //             card.name && projects.find(p => p.name === card.name && p.id === projectId)
    //                 ? { ...card, progress: newProgress }
    //                 : card
    //         )
    //     )
    // }

    const getGradientStyle = (progress) => {
        return {
            background: `linear-gradient(to right, #0258d8 ${progress}%, white 100%)`
        }
    }

    const renderCard = (card) => {
        switch (card.type) {
            case 'grid':
                return (
                    <div 
                        className='card card-grid' 
                        key={card.id}
                        style={getGradientStyle(card.progress)}
                    >
                        <div id='card-name-div'>
                            <p id='card-name'>{card.name}</p>
                            <p id='progress-text'>{card.progress}%</p>
                        </div>
                        <div id='bottom-row'>
                            <Link to='/' id='gear'/>
                            <div 
                                id='indicator' 
                                className={card.progress === 100 ? 'completed' : 'in-progress'}
                            ></div>
                        </div>
                    </div>
                )
            case 'new':
                return (
                    <div className='card new-card' key={card.id}>
                        <button className="add-project" onClick={() => addProject(card.id)}>
                            <p className='plus'>+</p>
                        </button>
                    </div>
                )
            case 'empty':
                return <div className='card' key={card.id}></div>
            default:
                return <div className='card' key={card.id}></div>
        }
    }

    return(
        <div id="travoman">
            <div className='homelink'><Link to='/' className='home'>Главная</Link></div>
            <div id="account">
                <aside id="accountpanel">
                    <div id="user">
                        <div id='ava'></div>
                        <div id='user-name'></div>
                    </div>
                    <div id='projects'>
                        <button id='buttproj' onClick={toggleList}>
                            <p id='butt-sign'>Проекты</p>
                        </button>
                        <ul id='list' className={isListVisible ? 'visible' : 'hidden'}>
                            {projects.map((project) => (
                                <li key={project.id}>
                                    {project.name} - {project.progress}%
                                </li>
                            ))}
                        </ul>
                    </div>
                </aside>

                <div className='cardsdiv' id='firstdiv'>
                    {cards.slice(0, 3).map(card => renderCard(card))}
                </div>
                <div className='cardsdiv' id='secdiv'>
                    {cards.slice(3, 6).map(card => renderCard(card))}
                </div>
            </div>
        </div>
    )
}