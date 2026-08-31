package com.dataagent.platform.modules.dataset.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dataagent.platform.modules.dataset.domain.po.DatasetPO;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface DatasetMapper extends BaseMapper<DatasetPO> {
}
