import { Select } from 'antd';
import { useTranslation } from 'react-i18next';
import { GlobalOutlined } from '@ant-design/icons';

const { Option } = Select;

const LanguageSwitcher = ({ style }) => {
    const { i18n, t } = useTranslation();

    const handleLanguageChange = (value) => {
        i18n.changeLanguage(value);
    };

    return (
        <Select
            value={i18n.language}
            onChange={handleLanguageChange}
            style={{ width: 120, ...style }}
            suffixIcon={<GlobalOutlined />}
        >
            <Option value="en">{t('language.english')}</Option>
            <Option value="zh">{t('language.chinese')}</Option>
        </Select>
    );
};

export default LanguageSwitcher;